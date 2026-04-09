import json
from datetime import datetime
from decimal import Decimal
from django.db import connection, transaction
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from django.utils import timezone
from milk_agency.models import OrderDelivery, SubscriptionDelivery, SubscriptionOrder
from milk_agency.order_pricing import get_customer_unit_price
from customer_portal.models import CustomerOrder, CustomerOrderItem
from customer_portal.order_workflow import finalize_order_after_payment
from api.user_api_helpers import find_linked_order_for_bill, get_delivery_charge_for_bill
from milk_agency.models import Bill


class SubscriptionDeliveryFallback:
    def __init__(self, subscription_order, status, delivered_at=None, bill=None):
        self.subscription_order = subscription_order
        self.status = status
        self.delivered_at = delivered_at
        self.bill = bill

    def get_status_display(self):
        return self.status.replace("_", " ").title()


def _table_exists(model):
    try:
        return model._meta.db_table in connection.introspection.table_names()
    except Exception:
        return False


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


def _order_grand_total(order):
    return Decimal(order.total_amount or 0) + Decimal(order.delivery_charge or 0)


def _present_order_status(raw_status):
    return "out_for_delivery" if raw_status == "confirmed" else (raw_status or "pending")


def _present_order_status_label(raw_status):
    return _present_order_status(raw_status).replace("_", " ").title()


def _clean_text(value):
    return str(value or "").strip().lower()


def _parse_filter_date(raw):
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _admin_order_detail_context(order):
    subtotal_amount = Decimal(order.approved_total_amount or order.total_amount or 0)
    display_total_amount = subtotal_amount + Decimal(order.delivery_charge or 0)
    savings_amount = max(Decimal(order.total_amount or 0) - subtotal_amount, Decimal("0.00"))
    bill = Bill.objects.filter(
        customer=order.customer,
        total_amount=order.approved_total_amount,
    ).order_by("-invoice_date").first()
    return {
        "order": order,
        "subtotal_amount": subtotal_amount,
        "display_total_amount": display_total_amount,
        "savings_amount": savings_amount,
        "bill": bill,
    }


def _resolve_order_status(order, has_order_delivery_table):
    delivery_tracking = getattr(order, "delivery_tracking", None) if has_order_delivery_table else None
    raw_status = (
        getattr(delivery_tracking, "status", None)
        or getattr(order, "status", None)
        or "pending"
    )
    return _present_order_status(raw_status)


def _matches_order(order, filters, has_order_delivery_table):
    if filters["kind"] not in ("all", "order"):
        return False
    if filters["stage"] == "pending" and _resolve_order_status(order, has_order_delivery_table) == "delivered":
        return False
    if filters["stage"] == "delivered" and _resolve_order_status(order, has_order_delivery_table) != "delivered":
        return False
    if filters["status"] != "all" and _resolve_order_status(order, has_order_delivery_table) != filters["status"]:
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


def _matches_subscription(delivery, filters, delivered_status):
    if filters["kind"] not in ("all", "subscription"):
        return False
    if filters["stage"] == "pending" and delivered_status == "delivered":
        return False
    if filters["stage"] == "delivered" and delivered_status != "delivered":
        return False
    if filters["status"] != "all" and delivery.status != filters["status"]:
        return False

    sub_order = delivery.subscription_order
    if filters["date"] and getattr(sub_order, "date", None) != filters["date"]:
        return False
    if filters["q"]:
        haystack = " ".join([
            getattr(getattr(sub_order, "customer", None), "name", ""),
            getattr(getattr(sub_order, "customer", None), "phone", ""),
            getattr(getattr(sub_order, "item", None), "name", ""),
        ]).lower()
        if filters["q"] not in haystack:
            return False
    return True


def _get_delivery_filters(request):
    raw_date = (request.GET.get("date") or "").strip()
    return {
        "q": _clean_text(request.GET.get("q")),
        "kind": (request.GET.get("kind") or "all").strip().lower(),
        "stage": (request.GET.get("stage") or "all").strip().lower(),
        "status": (request.GET.get("status") or "all").strip().lower(),
        "date_raw": raw_date,
        "date": _parse_filter_date(raw_date),
    }


# -------------------------------------------------------
# ADMIN ORDERS DASHBOARD
# -------------------------------------------------------
@never_cache
@login_required
def admin_orders_dashboard(request):
    pending_orders = CustomerOrder.objects.filter(status='pending').order_by('-order_date')

    return render(request, 'customer_portal/admin_orders_dashboard.html', {
        'pending_orders': pending_orders,
        'total_pending': pending_orders.count()
    })


@never_cache
@login_required
def customer_order_history(request, customer_id):
    customer = get_object_or_404(Customer.objects, id=customer_id)
    orders = (
        CustomerOrder.objects.filter(customer_id=customer_id)
        .select_related("customer", "approved_by")
        .order_by("-order_date", "-id")
    )
    for order in orders:
        order.display_total_amount = Decimal(order.approved_total_amount or order.total_amount or 0) + Decimal(order.delivery_charge or 0)

    return render(
        request,
        "milk_agency/orders/customer_order_history.html",
        {
            "history_customer": customer,
            "orders": orders,
        },
    )


@never_cache
@login_required
def admin_order_detail(request, order_id):
    order = get_object_or_404(
        CustomerOrder.objects.select_related("customer", "approved_by", "bill").prefetch_related("items__item"),
        id=order_id,
    )
    context = _admin_order_detail_context(order)
    return render(request, "milk_agency/orders/admin_order_detail.html", context)


@never_cache
@login_required
def admin_delivery_dashboard(request):
    today = timezone.localdate()
    filters = _get_delivery_filters(request)
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
            .select_related("customer", "approved_by", "delivery_tracking__delivered_by")
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
            .select_related("customer", "approved_by")
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
            .select_related(
                "subscription_order__customer",
                "subscription_order__item",
                "delivered_by",
                "bill",
            )
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

    for order in pending_orders + delivered_orders:
        raw_status = getattr(getattr(order, "delivery_tracking", None), "status", None) or getattr(order, "status", "pending")
        order.display_delivery_status = _present_order_status(raw_status)
        order.display_delivery_status_label = _present_order_status_label(raw_status)

    pending_orders_count = _safe_len_or_count(pending_orders)
    delivered_orders_count = _safe_len_or_count(delivered_orders)
    pending_subscriptions_count = _safe_len_or_count(pending_subscriptions)
    delivered_subscriptions_count = _safe_len_or_count(delivered_subscriptions)

    context = {
        "today": today,
        "pending_orders": pending_orders,
        "delivered_orders": delivered_orders,
        "pending_subscriptions": pending_subscriptions,
        "delivered_subscriptions": delivered_subscriptions,
        "has_order_delivery_table": has_order_delivery_table,
        "has_subscription_delivery_table": has_subscription_delivery_table,
        "pending_orders_count": pending_orders_count,
        "delivered_orders_count": delivered_orders_count,
        "pending_subscriptions_count": pending_subscriptions_count,
        "delivered_subscriptions_count": delivered_subscriptions_count,
        "pending_total": pending_orders_count + pending_subscriptions_count,
        "delivered_total": delivered_orders_count + delivered_subscriptions_count,
        "filters": filters,
    }
    return render(request, "milk_agency/dashboards_other/admin_delivery_dashboard.html", context)


# -------------------------------------------------------
# CONFIRM ORDER + GENERATE BILL (SAFE VERSION)
# -------------------------------------------------------
@never_cache
@login_required
def confirm_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON.'})

    quantities = data.get('quantities', [])
    order = get_object_or_404(CustomerOrder, id=order_id)

    # 🚨 Prevent double confirmation
    if order.status != 'pending':
        return JsonResponse({'success': False, 'message': 'Order already processed.'})

    try:
        with transaction.atomic():

            # -------- UPDATE ORDER ITEMS --------
            for q in quantities:
                item_id = q.get('item_id')
                quantity = int(q.get('quantity', 0))
                discount = Decimal(str(q.get('discount', 0)))

                if quantity < 0:
                    return JsonResponse({'success': False, 'message': 'Invalid quantity.'})
                if discount < 0:
                    return JsonResponse({'success': False, 'message': 'Invalid discount.'})

                if item_id is None:
                    continue

                try:
                    order_item = order.items.get(id=item_id)
                except CustomerOrderItem.DoesNotExist:
                    continue

                unit_price = get_customer_unit_price(order_item.item, order.customer)
                order_item.requested_quantity = quantity
                order_item.requested_price = unit_price
                order_item.approved_quantity = quantity
                order_item.approved_price = unit_price
                order_item.discount = discount
                order_item.discount_total = discount * quantity
                order_item.requested_total = (
                    unit_price * quantity
                ) - order_item.discount_total
                order_item.approved_total = order_item.requested_total
                order_item.save()

            # -------- RECALCULATE ORDER TOTAL --------
            total_amount = sum(
                (oi.requested_total or Decimal('0.00'))
                for oi in order.items.all()
            )
            order.total_amount = total_amount
            order.save()

            bill = finalize_order_after_payment(
                order,
                payment_reference=order.payment_reference or f"ADMIN-{order.order_number}",
                payment_method=order.payment_method or "ADMIN",
                approved_by=request.user,
                mark_paid=False,
            )[1]

            return JsonResponse({
                'success': True,
                'message': f'Order confirmed & bill {bill.invoice_number} generated.',
                'bill_id': bill.id
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


# -------------------------------------------------------
# REJECT ORDER
# -------------------------------------------------------
@never_cache
@login_required
def reject_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})

    order = get_object_or_404(CustomerOrder, id=order_id)

    if order.status != 'pending':
        return JsonResponse({'success': False, 'message': 'Order already processed.'})

    order.status = 'rejected'
    order.approved_by = request.user
    order.save()

    return JsonResponse({'success': True, 'message': 'Order rejected successfully.'})
