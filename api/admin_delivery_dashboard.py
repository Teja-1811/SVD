from datetime import datetime
from django.db import connection
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from customer_portal.models import CustomerOrder
from milk_agency.models import OrderDelivery, SubscriptionDelivery, SubscriptionOrder


class SubscriptionDeliveryFallback:
    def __init__(self, subscription_order, status, delivered_at=None, bill=None):
        self.subscription_order = subscription_order
        self.status = status
        self.delivered_at = delivered_at
        self.bill = bill

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


def _safe_len_or_count(value):
    try:
        return value.count()
    except TypeError:
        return len(value)


def _present_order_status(raw_status):
    return "out_for_delivery" if raw_status == "confirmed" else (raw_status or "pending")


def _present_order_status_label(raw_status):
    status = _present_order_status(raw_status)
    return status.replace("_", " ").title()


def _clean_text(value):
    return str(value or "").strip().lower()


def _parse_filter_date(raw):
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


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


def _order_status(order, has_order_delivery_table):
    delivery_tracking = getattr(order, "delivery_tracking", None) if has_order_delivery_table else None
    raw_status = (
        getattr(delivery_tracking, "status", None)
        or getattr(order, "status", None)
        or "pending"
    )
    return _present_order_status(raw_status)


def _matches_order(order, filters, has_order_delivery_table):
    status = _order_status(order, has_order_delivery_table)
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
        haystack = " ".join([
            getattr(order, "order_number", ""),
            getattr(getattr(order, "customer", None), "name", ""),
            getattr(getattr(order, "customer", None), "phone", ""),
            getattr(order, "delivery_address", ""),
        ]).lower()
        if filters["q"] not in haystack:
            return False
    return True


def _matches_subscription(delivery, filters, stage):
    if filters["kind"] not in ("all", "subscription"):
        return False
    if filters["stage"] == "pending" and stage == "delivered":
        return False
    if filters["stage"] == "delivered" and stage != "delivered":
        return False
    if filters["status"] != "all" and delivery.status != filters["status"]:
        return False
    order = delivery.subscription_order
    if filters["date"] and getattr(order, "date", None) != filters["date"]:
        return False
    if filters["q"]:
        haystack = " ".join([
            getattr(getattr(order, "customer", None), "name", ""),
            getattr(getattr(order, "customer", None), "phone", ""),
            getattr(getattr(order, "item", None), "name", ""),
        ]).lower()
        if filters["q"] not in haystack:
            return False
    return True


def _bill_payload(request, bill):
    if not bill:
        return None
    return {
        "bill_id": bill.id,
        "invoice_number": bill.invoice_number,
        "invoice_date": str(bill.invoice_date),
        "total_amount": float(bill.total_amount or 0),
        "view_url": request.build_absolute_uri(
            reverse("milk_agency:view_bill", args=[bill.id])
        ),
        "pdf_url": request.build_absolute_uri(
            reverse("milk_agency:generate_invoice_pdf", args=[bill.id])
        ),
    }


def _serialize_order(order, has_order_delivery_table):
    delivery_tracking = getattr(order, "delivery_tracking", None) if has_order_delivery_table else None
    raw_status = delivery_tracking.status if delivery_tracking and delivery_tracking.status else getattr(order, "status", "pending")
    status = _present_order_status(raw_status)
    delivered_at = delivery_tracking.delivered_at if delivery_tracking and delivery_tracking.delivered_at else None

    grand_total = float((order.total_amount or 0) + (order.delivery_charge or 0))
    return {
        "type": "order",
        "order_id": order.id,
        "order_number": order.order_number,
        "customer_id": order.customer.id if order.customer else None,
        "customer_name": order.customer.name if order.customer else "",
        "phone": order.customer.phone if order.customer else "",
        "delivery_date": str(order.delivery_date),
        "order_date": str(order.order_date),
        "status": status,
        "status_label": delivery_tracking.get_status_display() if delivery_tracking and raw_status != "confirmed" else _present_order_status_label(raw_status),
        "total_amount": float(order.total_amount or 0),
        "delivery_charge": float(order.delivery_charge or 0),
        "grand_total": grand_total,
        "delivery_address": order.delivery_address or "",
        "delivered_at": delivered_at.isoformat() if delivered_at else None,
    }


def _serialize_subscription_delivery(request, delivery):
    order = delivery.subscription_order
    return {
        "type": "subscription",
        "delivery_id": getattr(delivery, "id", None),
        "subscription_order_id": order.id,
        "subscription_id": order.subscription_id,
        "customer_id": order.customer.id if order.customer else None,
        "customer_name": order.customer.name if order.customer else "",
        "phone": order.customer.phone if order.customer else "",
        "item_id": order.item.id if order.item else None,
        "item_name": order.item.name if order.item else "",
        "quantity": order.quantity,
        "date": str(order.date),
        "status": delivery.status,
        "status_label": delivery.get_status_display(),
        "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
        "bill": _bill_payload(request, getattr(delivery, "bill", None)),
    }


@api_view(["GET"])
def api_admin_delivery_dashboard(request):
    today = timezone.localdate()
    filters = _get_filters(request)
    has_order_delivery_table = _model_is_queryable(OrderDelivery)
    has_subscription_delivery_table = _model_is_queryable(SubscriptionDelivery)

    if has_order_delivery_table:
        pending_orders = (
            CustomerOrder.objects
            .select_related("customer")
            .filter(
                Q(status__in=["pending", "confirmed", "processing", "ready"]) |
                Q(delivery_tracking__status__in=["pending", "out_for_delivery", "failed"])
            )
            .exclude(status__in=["rejected", "cancelled", "delivered"])
            .distinct()
            .order_by("delivery_date", "-order_date")
        )
        delivered_orders = (
            CustomerOrder.objects
            .select_related("customer", "delivery_tracking__delivered_by")
            .filter(Q(status="delivered") | Q(delivery_tracking__status="delivered"))
            .distinct()
            .order_by("-delivery_date", "-updated_at")
        )
    else:
        pending_orders = (
            CustomerOrder.objects
            .select_related("customer")
            .filter(status__in=["pending", "confirmed", "processing", "ready"])
            .exclude(status__in=["rejected", "cancelled", "delivered"])
            .order_by("delivery_date", "-order_date")
        )
        delivered_orders = (
            CustomerOrder.objects
            .select_related("customer")
            .filter(status="delivered")
            .order_by("-delivery_date", "-updated_at")
        )

    if has_subscription_delivery_table:
        pending_subscriptions = (
            SubscriptionDelivery.objects
            .select_related("subscription_order__customer", "subscription_order__item", "bill")
            .filter(status__in=["pending", "out_for_delivery"])
            .order_by("subscription_order__date", "subscription_order__customer__name")
        )
        delivered_subscriptions = (
            SubscriptionDelivery.objects
            .select_related("subscription_order__customer", "subscription_order__item", "bill")
            .filter(status="delivered")
            .order_by("-subscription_order__date", "-delivered_at", "-updated_at")
        )
    else:
        pending_subscriptions = [
            SubscriptionDeliveryFallback(subscription_order=obj, status="pending")
            for obj in SubscriptionOrder.objects
            .select_related("customer", "item")
            .filter(delivered=False)
            .order_by("date", "customer__name")
        ]
        delivered_subscriptions = [
            SubscriptionDeliveryFallback(subscription_order=obj, status="delivered")
            for obj in SubscriptionOrder.objects
            .select_related("customer", "item")
            .filter(delivered=True)
            .order_by("-date", "customer__name")
        ]

    pending_orders = [
        order for order in pending_orders
        if _matches_order(order, filters, has_order_delivery_table)
    ]
    delivered_orders = [
        order for order in delivered_orders
        if _matches_order(order, filters, has_order_delivery_table)
    ]
    pending_subscriptions = [
        delivery for delivery in pending_subscriptions
        if _matches_subscription(delivery, filters, "pending")
    ]
    delivered_subscriptions = [
        delivery for delivery in delivered_subscriptions
        if _matches_subscription(delivery, filters, "delivered")
    ]

    pending_orders_list = [_serialize_order(order, has_order_delivery_table) for order in pending_orders]
    delivered_orders_list = [_serialize_order(order, has_order_delivery_table) for order in delivered_orders]
    pending_subscriptions_list = [_serialize_subscription_delivery(request, delivery) for delivery in pending_subscriptions]
    delivered_subscriptions_list = [_serialize_subscription_delivery(request, delivery) for delivery in delivered_subscriptions]

    return Response({
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
        "summary": {
            "pending_orders": _safe_len_or_count(pending_orders_list),
            "pending_subscriptions": _safe_len_or_count(pending_subscriptions_list),
            "delivered_orders": _safe_len_or_count(delivered_orders_list),
            "delivered_subscriptions": _safe_len_or_count(delivered_subscriptions_list),
            "pending_total": _safe_len_or_count(pending_orders_list) + _safe_len_or_count(pending_subscriptions_list),
            "delivered_total": _safe_len_or_count(delivered_orders_list) + _safe_len_or_count(delivered_subscriptions_list),
        },
        "pending_customer_orders": pending_orders_list,
        "pending_subscriptions": pending_subscriptions_list,
        "delivered_customer_orders": delivered_orders_list,
        "delivered_subscriptions": delivered_subscriptions_list,
    })
