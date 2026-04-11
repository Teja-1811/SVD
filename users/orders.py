from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from decimal import Decimal
import json

from api.order_creator import can_delete_order, delete_order
from customer_portal.models import CustomerOrder
from milk_agency.models import CustomerPayment
from .helpers import (
    active_orders,
    grouped_catalog,
    minimum_prebook_date,
    save_user_order,
    save_user_order_response,
    user_required,
)

from milk_agency.paytm import _paytm_base_url, initiate_order_transaction


def _paytm_diagnostics(request):
    try:
        from paytmchecksum import PaytmChecksum  # noqa: F401
        package_loaded = True
        import_error = ""
    except Exception as exc:
        package_loaded = False
        import_error = str(exc)

    callback_url = getattr(settings, "PAYTM_CALLBACK_URL", "").strip()
    if callback_url.startswith("/"):
        callback_url = request.build_absolute_uri(callback_url)

    website = str(getattr(settings, "PAYTM_WEBSITE", "") or "").strip()
    environment = str(getattr(settings, "PAYTM_ENV", "") or "").strip()
    checkout_host = _paytm_base_url()

    latest_gateway_attempt = (
        CustomerOrder.objects.filter(customer=request.user)
        .exclude(gateway_order_id="")
        .order_by("-updated_at", "-id")
        .first()
    )
    latest_payment_attempt = None
    if latest_gateway_attempt and latest_gateway_attempt.gateway_order_id:
        latest_payment_attempt = (
            CustomerPayment.objects.filter(payment_order_id=latest_gateway_attempt.gateway_order_id)
            .order_by("-created_at", "-id")
            .first()
        )

    return {
        "package_loaded": package_loaded,
        "import_error": import_error,
        "mid_present": bool(str(getattr(settings, "PAYTM_MID", "") or "").strip()),
        "merchant_key_present": bool(str(getattr(settings, "PAYTM_MERCHANT_KEY", "") or "").strip()),
        "environment": environment or ("staging" if website.upper() == "WEBSTAGING" else "production"),
        "website": website or "Not configured",
        "base_url": checkout_host,
        "callback_url": callback_url,
        "webhook_url": "Not configured",
        "latest_gateway_attempt": latest_gateway_attempt,
        "latest_payment_attempt": latest_payment_attempt,
        "latest_paytm_response": (
            latest_payment_attempt.callback_payload
            if latest_payment_attempt and latest_payment_attempt.callback_payload
            else None
        ),
        "checkout_js_url": (
            f"{checkout_host}/merchantpgpui/checkoutjs/merchants/{settings.PAYTM_MID}.js"
            if str(getattr(settings, "PAYTM_MID", "") or "").strip()
            else ""
        ),
    }


@user_required
def orders_page(request):
    orders = active_orders(request.user)
    diagnostics = _paytm_diagnostics(request)

    return render(
        request,
        "user_portal/orders.html",
        {
            "available_items_by_category": grouped_catalog(request.user, include_out_of_stock=False),
            "prebook_items_by_category": grouped_catalog(request.user, include_out_of_stock=True),
            "active_orders": orders,
            "min_prebooking_date": minimum_prebook_date(),
            "paytm_diagnostics": diagnostics,
            "latest_gateway_attempt": diagnostics["latest_gateway_attempt"],
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
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request."}, status=400)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)

    try:
        order = save_user_order(
            customer=request.user,
            raw_items=payload.get("items", []),
            raw_delivery_date=str(payload.get("delivery_date") or "").strip(),
            payment_method="PAYTM",
            initial_status="payment_pending",
        )
        payment_result = initiate_order_transaction(order)
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"success": False, "message": f"Unable to prepare payment: {exc}"}, status=502)

    if not payment_result.get("success") or not payment_result.get("txnToken"):
        paytm_response = payment_result.get("paytm_response") or {}
        message = payment_result.get("message") or "Paytm did not return a transaction token."
        result_info = ((paytm_response.get("body") or {}).get("resultInfo") or {}) if isinstance(paytm_response, dict) else {}
        return JsonResponse(
            {
                "success": False,
                "message": message,
                "payment_order_id": payment_result.get("payment_order_id", ""),
                "paytm_result_status": result_info.get("resultStatus", ""),
                "paytm_result_code": result_info.get("resultCode", ""),
            },
            status=502,
        )

    checkout_host = _paytm_base_url()
    return JsonResponse(
        {
            "success": True,
            "order_id": order.id,
            "order_number": order.order_number,
            "payment_order_id": payment_result["payment_order_id"],
            "txnToken": payment_result["txnToken"],
            "mid": settings.PAYTM_MID,
            "amount": f"{Decimal(payment_result['amount']):.2f}",
            "checkout_host": checkout_host,
            "checkout_js_url": f"{checkout_host}/merchantpgpui/checkoutjs/merchants/{settings.PAYTM_MID}.js",
        }
    )


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


@user_required
def delete_order_page(request, order_id):
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect("users:order_history")

    order = get_object_or_404(CustomerOrder.objects.filter(customer=request.user), id=order_id)
    if not can_delete_order(order):
        messages.error(request, "Only payment pending orders can be deleted.")
        return redirect("users:order_detail", order_id=order_id)

    if delete_order(request.user, order_id):
        messages.success(request, f"Order {order.order_number} deleted successfully.")
        return redirect("users:order_history")

    messages.error(request, "Unable to delete this order.")
    return redirect("users:order_detail", order_id=order_id)
