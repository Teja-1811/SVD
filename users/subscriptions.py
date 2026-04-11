import json
from decimal import Decimal

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render

from .helpers import subscription_context, user_required
from milk_agency.paytm import _paytm_base_url, initiate_subscription_transaction


@user_required
def subscriptions_page(request):
    subscription, items = subscription_context(request.user)
    return render(
        request,
        "user_portal/subscriptions.html",
        {
            "subscription": subscription,
            "subscription_items": items,
        },
    )


@user_required
def prepare_subscription_payment(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request."}, status=400)

    subscription, _items = subscription_context(request.user)
    if not subscription:
        return JsonResponse({"success": False, "message": "No active subscription found."}, status=404)

    try:
        payload = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)

    raw_amount = payload.get("amount")
    amount = None
    if raw_amount not in (None, ""):
        try:
            amount = Decimal(raw_amount)
        except Exception:
            return JsonResponse({"success": False, "message": "Invalid amount."}, status=400)

    try:
        payment_result = initiate_subscription_transaction(
            subscription=subscription,
            amount=amount,
            request=request,
        )
    except Exception as exc:
        return JsonResponse({"success": False, "message": f"Unable to prepare subscription payment: {exc}"}, status=502)

    if not payment_result.get("success") or not payment_result.get("txnToken"):
        paytm_response = payment_result.get("paytm_response") or {}
        result_info = ((paytm_response.get("body") or {}).get("resultInfo") or {}) if isinstance(paytm_response, dict) else {}
        return JsonResponse(
            {
                "success": False,
                "message": payment_result.get("message") or "Paytm did not return a transaction token.",
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
            "subscription_id": subscription.id,
            "payment_order_id": payment_result["payment_order_id"],
            "txnToken": payment_result["txnToken"],
            "mid": settings.PAYTM_MID,
            "amount": f"{Decimal(payment_result['amount']):.2f}",
            "checkout_host": checkout_host,
            "checkout_js_url": f"{checkout_host}/merchantpgpui/checkoutjs/merchants/{settings.PAYTM_MID}.js",
        }
    )
