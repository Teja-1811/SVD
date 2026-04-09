from datetime import datetime

from django.db import connection
from django.db.models import Q
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from customer_portal.models import CustomerOrder
from milk_agency.models import OrderDelivery, SubscriptionDelivery, SubscriptionOrder


ORDER_PENDING_STATUSES = {"pending", "confirmed", "processing", "ready", "payment_pending"}
ORDER_CLOSED_STATUSES = {"rejected", "cancelled", "delivered"}
ORDER_TRACKING_PENDING_STATUSES = {"pending", "out_for_delivery", "failed"}
SUBSCRIPTION_PENDING_STATUSES = {"pending", "out_for_delivery", "failed", "skipped"}


class SubscriptionDeliveryFallback:
    def __init__(self, subscription_order, status, delivered_at=None, bill=None):
        self.id = None
        self.subscription_order = subscription_order
        self.status = status
        self.delivered_at = delivered_at
        self.bill = bill
        self.eta = None
        self.delivered_by = None
        self.notes = ""
        self.created_at = getattr(subscription_order, "created_at", None)
        self.updated_at = getattr(subscription_order, "created_at", None)

    def get_status_display(self):
        return self.status.replace("_", " ").title()


def _model_is_queryable(model):
    try:
        table_names = connection.introspection.table_names()
        if model._meta.db_table not in table_names:
            return False

        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, model._meta.db_table)
        db_columns = {col.name for col in description}
        model_columns = {
            field.column
            for field in model._meta.local_concrete_fields
            if getattr(field, "column", None)
        }
        return model_columns.issubset(db_columns)
    except Exception:
        return False


def _parse_filter_date(raw):
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _clean_text(value):
    return str(value or "").strip().lower()


def _get_filters(request):
    raw_date = (request.GET.get("date") or "").strip()
    return {
        "q": _clean_text(request.GET.get("q")),
        "kind": (request.GET.get("kind") or "all").strip().lower(),
        "stage": (request.GET.get("stage") or "all").strip().lower(),
        "status": (request.GET.get("status") or "all").strip().lower(),
        "date_raw": raw_date,
        "date": _parse_filter_date(raw_date),
    }


def _present_order_status(raw_status):
    status = (raw_status or "pending").strip().lower()
    if status == "confirmed":
        return "out_for_delivery"
    if status == "processing":
        return "out_for_delivery"
    if status == "ready":
        return "pending"
    return status


def _status_label(status):
    return str(status or "").replace("_", " ").title()


def _iso(dt):
    return dt.isoformat() if dt else None


def _absolute_url(request, route_name, *args):
    try:
        return request.build_absolute_uri(reverse(route_name, args=args))
    except NoReverseMatch:
        return None


def _bill_payload(request, bill):
    if not bill:
        return None
    return {
        "bill_id": bill.id,
        "invoice_number": bill.invoice_number,
        "invoice_date": str(bill.invoice_date),
        "total_amount": float(bill.total_amount or 0),
        "view_url": _absolute_url(request, "milk_agency:view_bill", bill.id),
        "pdf_url": _absolute_url(request, "milk_agency:generate_invoice_pdf", bill.id),
    }


def _customer_payload(customer):
    if not customer:
        return {
            "customer_id": None,
            "name": "",
            "phone": "",
            "user_type": "",
        }
    return {
        "customer_id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "user_type": getattr(customer, "user_type", ""),
    }


def _staff_payload(user):
    if not user:
        return None
    name = getattr(user, "name", "") or getattr(user, "username", "") or getattr(user, "phone", "")
    return {
        "id": user.id,
        "name": name,
        "phone": getattr(user, "phone", ""),
    }


def _resolve_order_tracking(order, has_order_delivery_table):
    return getattr(order, "delivery_tracking", None) if has_order_delivery_table else None


def _resolve_order_status(order, has_order_delivery_table):
    delivery_tracking = _resolve_order_tracking(order, has_order_delivery_table)
    raw_status = getattr(delivery_tracking, "status", None) or getattr(order, "status", None) or "pending"
    return _present_order_status(raw_status)


def _matches_order(order, filters, has_order_delivery_table):
    status = _resolve_order_status(order, has_order_delivery_table)
    if filters["kind"] not in ("all", "order"):
        return False
    if filters["stage"] == "pending" and status == "delivered":
        return False
    if filters["stage"] == "delivered" and status != "delivered":
        return False
    if filters["status"] != "all" and status != filters["status"]:
        return False
    if filters["date"] and getattr(order, "delivery_date", None) != filters["date"]:
        return False
    if filters["q"]:
        haystack = " ".join(
            [
                getattr(order, "order_number", ""),
                getattr(getattr(order, "customer", None), "name", ""),
                getattr(getattr(order, "customer", None), "phone", ""),
                getattr(order, "delivery_address", ""),
                getattr(order, "payment_reference", ""),
            ]
        ).lower()
        if filters["q"] not in haystack:
            return False
    return True


def _matches_subscription(delivery, filters):
    if filters["kind"] not in ("all", "subscription"):
        return False
    if filters["stage"] == "pending" and delivery.status == "delivered":
        return False
    if filters["stage"] == "delivered" and delivery.status != "delivered":
        return False
    if filters["status"] != "all" and delivery.status != filters["status"]:
        return False

    sub_order = delivery.subscription_order
    if filters["date"] and getattr(sub_order, "date", None) != filters["date"]:
        return False
    if filters["q"]:
        haystack = " ".join(
            [
                getattr(getattr(sub_order, "customer", None), "name", ""),
                getattr(getattr(sub_order, "customer", None), "phone", ""),
                getattr(getattr(sub_order, "item", None), "name", ""),
                getattr(getattr(getattr(sub_order, "subscription", None), "subscription_plan", None), "name", ""),
            ]
        ).lower()
        if filters["q"] not in haystack:
            return False
    return True


def _serialize_order(order, request, has_order_delivery_table):
    delivery_tracking = _resolve_order_tracking(order, has_order_delivery_table)
    status = _resolve_order_status(order, has_order_delivery_table)
    delivery_charge = float(order.delivery_charge or 0)
    items_total = float(order.total_amount or 0)
    grand_total = items_total + delivery_charge

    return {
        "type": "order",
        "order_id": order.id,
        "order_number": order.order_number,
        "customer": _customer_payload(order.customer),
        "order_date": str(order.order_date),
        "delivery_date": str(order.delivery_date),
        "status": status,
        "status_label": _status_label(status),
        "order_status_raw": getattr(order, "status", ""),
        "tracking_status_raw": getattr(delivery_tracking, "status", None),
        "tracking_available": bool(delivery_tracking),
        "items_total": items_total,
        "delivery_charge": delivery_charge,
        "grand_total": grand_total,
        "approved_total_amount": float(order.approved_total_amount or 0),
        "delivery_address": order.delivery_address or "",
        "payment_method": order.payment_method or "",
        "payment_status": order.payment_status or "",
        "payment_reference": order.payment_reference or "",
        "payment_confirmed_at": _iso(order.payment_confirmed_at),
        "eta": _iso(getattr(delivery_tracking, "eta", None)),
        "delivered_at": _iso(getattr(delivery_tracking, "delivered_at", None)),
        "delivered_amount": float(getattr(delivery_tracking, "delivered_amount", 0) or 0),
        "delivery_notes": getattr(delivery_tracking, "notes", "") or "",
        "delivered_by": _staff_payload(getattr(delivery_tracking, "delivered_by", None)),
        "approved_by": _staff_payload(getattr(order, "approved_by", None)),
        "bill": _bill_payload(request, getattr(order, "bill", None)),
        "items_count": order.items.count(),
        "created_at": _iso(getattr(order, "created_at", None)),
        "updated_at": _iso(getattr(order, "updated_at", None)),
    }


def _serialize_subscription_delivery(delivery, request):
    order = delivery.subscription_order
    subscription = getattr(order, "subscription", None)
    plan = getattr(subscription, "subscription_plan", None)

    return {
        "type": "subscription",
        "delivery_id": getattr(delivery, "id", None),
        "subscription_order_id": order.id,
        "subscription_id": order.subscription_id,
        "customer": _customer_payload(order.customer),
        "plan": {
            "id": plan.id if plan else None,
            "name": plan.name if plan else "",
        },
        "item": {
            "id": order.item.id if order.item else None,
            "name": order.item.name if order.item else "",
        },
        "date": str(order.date),
        "quantity": order.quantity,
        "status": delivery.status,
        "status_label": delivery.get_status_display(),
        "delivered_flag": bool(order.delivered),
        "eta": _iso(getattr(delivery, "eta", None)),
        "delivered_at": _iso(getattr(delivery, "delivered_at", None)),
        "delivery_notes": getattr(delivery, "notes", "") or "",
        "delivered_by": _staff_payload(getattr(delivery, "delivered_by", None)),
        "bill": _bill_payload(request, getattr(delivery, "bill", None)),
        "created_at": _iso(getattr(delivery, "created_at", None)),
        "updated_at": _iso(getattr(delivery, "updated_at", None)),
    }


def _build_summary(today, pending_orders, delivered_orders, pending_subs, delivered_subs):
    today_pending_orders = sum(1 for order in pending_orders if str(order.get("delivery_date")) == str(today))
    today_delivered_orders = sum(1 for order in delivered_orders if str(order.get("delivery_date")) == str(today))
    today_pending_subs = sum(1 for item in pending_subs if str(item.get("date")) == str(today))
    today_delivered_subs = sum(1 for item in delivered_subs if str(item.get("date")) == str(today))

    return {
        "pending_orders": len(pending_orders),
        "delivered_orders": len(delivered_orders),
        "pending_subscriptions": len(pending_subs),
        "delivered_subscriptions": len(delivered_subs),
        "pending_total": len(pending_orders) + len(pending_subs),
        "delivered_total": len(delivered_orders) + len(delivered_subs),
        "today_pending_orders": today_pending_orders,
        "today_delivered_orders": today_delivered_orders,
        "today_pending_subscriptions": today_pending_subs,
        "today_delivered_subscriptions": today_delivered_subs,
        "today_total": today_pending_orders + today_delivered_orders + today_pending_subs + today_delivered_subs,
    }


@api_view(["GET"])
def api_admin_delivery_dashboard(request):
    today = timezone.localdate()
    filters = _get_filters(request)
    has_order_delivery_table = _model_is_queryable(OrderDelivery)
    has_subscription_delivery_table = _model_is_queryable(SubscriptionDelivery)

    if has_order_delivery_table:
        pending_orders_qs = (
            CustomerOrder.objects.select_related(
                "customer",
                "approved_by",
                "bill",
                "delivery_tracking__delivered_by",
            )
            .prefetch_related("items")
            .filter(
                Q(status__in=ORDER_PENDING_STATUSES)
                | Q(delivery_tracking__status__in=ORDER_TRACKING_PENDING_STATUSES)
            )
            .exclude(status__in=ORDER_CLOSED_STATUSES)
            .distinct()
            .order_by("delivery_date", "-order_date", "-created_at")
        )
        delivered_orders_qs = (
            CustomerOrder.objects.select_related(
                "customer",
                "approved_by",
                "bill",
                "delivery_tracking__delivered_by",
            )
            .prefetch_related("items")
            .filter(Q(status="delivered") | Q(delivery_tracking__status="delivered"))
            .distinct()
            .order_by("-delivery_date", "-updated_at")
        )
    else:
        pending_orders_qs = (
            CustomerOrder.objects.select_related("customer", "approved_by", "bill")
            .prefetch_related("items")
            .filter(status__in=ORDER_PENDING_STATUSES)
            .exclude(status__in=ORDER_CLOSED_STATUSES)
            .order_by("delivery_date", "-order_date", "-created_at")
        )
        delivered_orders_qs = (
            CustomerOrder.objects.select_related("customer", "approved_by", "bill")
            .prefetch_related("items")
            .filter(status="delivered")
            .order_by("-delivery_date", "-updated_at")
        )

    pending_orders = [
        _serialize_order(order, request, has_order_delivery_table)
        for order in pending_orders_qs
        if _matches_order(order, filters, has_order_delivery_table)
    ]
    delivered_orders = [
        _serialize_order(order, request, has_order_delivery_table)
        for order in delivered_orders_qs
        if _matches_order(order, filters, has_order_delivery_table)
    ]

    if has_subscription_delivery_table:
        pending_sub_qs = (
            SubscriptionDelivery.objects.select_related(
                "subscription_order__customer",
                "subscription_order__item",
                "subscription_order__subscription__subscription_plan",
                "delivered_by",
                "bill",
            )
            .filter(status__in=SUBSCRIPTION_PENDING_STATUSES)
            .order_by("subscription_order__date", "subscription_order__customer__name")
        )
        delivered_sub_qs = (
            SubscriptionDelivery.objects.select_related(
                "subscription_order__customer",
                "subscription_order__item",
                "subscription_order__subscription__subscription_plan",
                "delivered_by",
                "bill",
            )
            .filter(status="delivered")
            .order_by("-subscription_order__date", "-delivered_at", "-updated_at")
        )
        pending_subscriptions = [
            _serialize_subscription_delivery(delivery, request)
            for delivery in pending_sub_qs
            if _matches_subscription(delivery, filters)
        ]
        delivered_subscriptions = [
            _serialize_subscription_delivery(delivery, request)
            for delivery in delivered_sub_qs
            if _matches_subscription(delivery, filters)
        ]
    else:
        pending_sub_fallback = [
            SubscriptionDeliveryFallback(subscription_order=obj, status="pending")
            for obj in SubscriptionOrder.objects.select_related(
                "customer",
                "item",
                "subscription__subscription_plan",
            )
            .filter(delivered=False)
            .order_by("date", "customer__name")
        ]
        delivered_sub_fallback = [
            SubscriptionDeliveryFallback(subscription_order=obj, status="delivered")
            for obj in SubscriptionOrder.objects.select_related(
                "customer",
                "item",
                "subscription__subscription_plan",
            )
            .filter(delivered=True)
            .order_by("-date", "customer__name")
        ]
        pending_subscriptions = [
            _serialize_subscription_delivery(delivery, request)
            for delivery in pending_sub_fallback
            if _matches_subscription(delivery, filters)
        ]
        delivered_subscriptions = [
            _serialize_subscription_delivery(delivery, request)
            for delivery in delivered_sub_fallback
            if _matches_subscription(delivery, filters)
        ]

    summary = _build_summary(
        today=today,
        pending_orders=pending_orders,
        delivered_orders=delivered_orders,
        pending_subs=pending_subscriptions,
        delivered_subs=delivered_subscriptions,
    )

    return Response(
        {
            "date": str(today),
            "filters": {
                "q": filters["q"],
                "kind": filters["kind"],
                "stage": filters["stage"],
                "status": filters["status"],
                "date": filters["date_raw"],
            },
            "has_order_delivery_tracking": has_order_delivery_table,
            "has_subscription_delivery_tracking": has_subscription_delivery_table,
            "summary": summary,
            "pending_customer_orders": pending_orders,
            "delivered_customer_orders": delivered_orders,
            "pending_subscriptions": pending_subscriptions,
            "delivered_subscriptions": delivered_subscriptions,
            "status_options": {
                "order": ["pending", "out_for_delivery", "delivered", "failed"],
                "subscription": ["pending", "out_for_delivery", "delivered", "skipped", "failed"],
            },
        }
    )
