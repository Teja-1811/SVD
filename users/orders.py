from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from decimal import Decimal

from customer_portal.models import CustomerOrder
from .helpers import (
    active_orders,
    grouped_catalog,
    minimum_prebook_date,
    prepare_user_payment_order_response,
    save_user_order_response,
    user_required,
)


@user_required
def orders_page(request):
    return render(
        request,
        "user_portal/orders.html",
        {
            "available_items_by_category": grouped_catalog(request.user, include_out_of_stock=False),
            "prebook_items_by_category": grouped_catalog(request.user, include_out_of_stock=True),
            "active_orders": active_orders(request.user),
            "min_prebooking_date": minimum_prebook_date(),
        },
    )


@user_required
def order_history_page(request):
    orders = list(
        CustomerOrder.objects.filter(customer=request.user)
        .order_by("-order_date", "-id")
    )
    for order in orders:
        order.display_total_amount = Decimal(order.approved_total_amount or order.total_amount or 0) + Decimal(order.delivery_charge or 0)
    return render(
        request,
        "user_portal/order_history.html",
        {
            "orders": orders,
        },
    )


@user_required
def order_detail_page(request, order_id):
    order = get_object_or_404(
        CustomerOrder.objects.filter(customer=request.user).prefetch_related("items__item"),
        id=order_id,
    )
    subtotal_amount = Decimal(order.approved_total_amount or order.total_amount or 0)
    display_total_amount = subtotal_amount + Decimal(order.delivery_charge or 0)
    savings_amount = max(Decimal(order.total_amount or 0) - subtotal_amount, Decimal("0.00"))
    return render(
        request,
        "user_portal/order_detail.html",
        {
            "order": order,
            "subtotal_amount": subtotal_amount,
            "display_total_amount": display_total_amount,
            "savings_amount": savings_amount,
        },
    )


@user_required
def place_order(request):
    return save_user_order_response(request)


@user_required
def prepare_payment_order(request):
    return prepare_user_payment_order_response(request)


@user_required
def cancel_order(request, order_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request."}, status=400)

    order = get_object_or_404(active_orders(request.user), id=order_id)
    if order.status not in {"pending", "payment_pending"}:
        return JsonResponse({"success": False, "message": "Only open orders can be cancelled."}, status=400)

    order.status = "cancelled"
    if order.payment_status == "pending":
        order.payment_status = "failed"
        order.save(update_fields=["status", "payment_status", "updated_at"])
    else:
        order.save(update_fields=["status", "updated_at"])
    return JsonResponse({"success": True, "message": "Order cancelled successfully."})
