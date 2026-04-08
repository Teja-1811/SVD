from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

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
