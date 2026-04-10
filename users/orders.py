from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt

from api.paytm import get_paytm_diagnostics
from customer_portal.models import CustomerOrder
from api.paytm_notifications import extract_paytm_params, process_paytm_notification
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
    orders = active_orders(request.user)
    latest_gateway_attempt = (
        CustomerOrder.objects.filter(
            customer=request.user,
            payment_method__iexact="PAYTM",
        )
        .exclude(payment_method="")
        .order_by("-updated_at", "-id")
        .first()
    )
    paytm_diagnostics = get_paytm_diagnostics(
        request,
        callback_url_name="users:paytm_callback",
    )
    paytm_diagnostics["webhook_url"] = request.build_absolute_uri(reverse("paytm_payment_webhook"))

    return render(
        request,
        "user_portal/orders.html",
        {
            "available_items_by_category": grouped_catalog(request.user, include_out_of_stock=False),
            "prebook_items_by_category": grouped_catalog(request.user, include_out_of_stock=True),
            "active_orders": orders,
            "min_prebooking_date": minimum_prebook_date(),
            "latest_gateway_attempt": latest_gateway_attempt,
            "paytm_diagnostics": paytm_diagnostics,
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
def paytm_checkout(request, order_id):
    order = get_object_or_404(CustomerOrder, id=order_id, customer=request.user)
    paytm_checkout_map = request.session.get("paytm_checkout_map", {})
    checkout = paytm_checkout_map.get(str(order.id))
    if not checkout:
        messages.error(request, "The Paytm session expired. Please try the payment again.")
        return redirect("users:orders")
    return render(
        request,
        "user_portal/paytm_checkout.html",
        {
            "order": order,
            "checkout": checkout,
        },
    )

@csrf_exempt
def paytm_callback(request):
    params = extract_paytm_params(request)
    if not params and request.method == "GET":
        params = request.GET.dict()

    result = process_paytm_notification(params)
    order = result.get("order")
    order_id = getattr(order, "id", None)

    if order_id:
        paytm_checkout_map = request.session.get("paytm_checkout_map", {})
        if str(order_id) in paytm_checkout_map:
            paytm_checkout_map.pop(str(order_id), None)
            request.session["paytm_checkout_map"] = paytm_checkout_map
            request.session.modified = True

    if result["success"]:
        messages.success(request, result["message"])
    else:
        messages.error(request, result["message"])

    if order_id:
        return redirect("users:order_detail", order_id=order_id)
    return redirect("users:orders")


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
