import json
from decimal import Decimal
from django.db import connection, transaction
from django.db.models import Q
from milk_agency.views_bills import generate_bill_from_order
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from django.utils import timezone
from milk_agency.models import OrderDelivery, SubscriptionDelivery, SubscriptionOrder
from customer_portal.models import CustomerOrder, CustomerOrderItem


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
def admin_delivery_dashboard(request):
    today = timezone.localdate()
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

                order_item.requested_quantity = quantity
                order_item.discount = discount
                order_item.discount_total = discount * quantity
                order_item.requested_total = (
                    order_item.requested_price * quantity
                ) - order_item.discount_total
                order_item.save()

            # -------- RECALCULATE ORDER TOTAL --------
            total_amount = sum(
                (oi.requested_total or Decimal('0.00'))
                for oi in order.items.all()
            )
            order.total_amount = total_amount
            order.save()

            # -------- GENERATE BILL FIRST --------
            bill = generate_bill_from_order(order)

            # -------- MARK ORDER CONFIRMED --------
            order.status = 'confirmed'
            order.approved_by = request.user
            order.save()

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
