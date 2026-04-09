import json
import os

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from customer_portal.models import CustomerOrder
from customer_portal.order_workflow import finalize_order_after_payment


def _configured_confirm_token():
    return (
        os.environ.get("PAYMENT_GATEWAY_CONFIRM_TOKEN")
        or getattr(settings, "PAYMENT_GATEWAY_CONFIRM_TOKEN", "")
    ).strip()


def _is_authorized(request):
    configured_token = _configured_confirm_token()
    if not configured_token:
        return False

    provided_token = (
        request.headers.get("X-Payment-Confirm-Token")
        or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    ).strip()
    return provided_token == configured_token


@csrf_exempt
@require_POST
def confirm_order_payment_api(request):
    if not _is_authorized(request):
        return JsonResponse({"success": False, "message": "Unauthorized payment confirmation request."}, status=401)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)

    order_id = payload.get("order_id")
    order_number = str(payload.get("order_number") or "").strip()
    payment_reference = str(payload.get("transaction_id") or payload.get("payment_reference") or "").strip()
    payment_method = str(payload.get("payment_method") or "UPI").strip() or "UPI"
    payment_status = str(payload.get("status") or "").strip().lower()

    if not payment_reference:
        return JsonResponse({"success": False, "message": "payment_reference is required."}, status=400)

    if payment_status not in {"success", "captured", "paid"}:
        return JsonResponse({"success": False, "message": "Payment is not confirmed yet."}, status=400)

    order = None
    if order_id:
        order = CustomerOrder.objects.filter(id=order_id).first()
    elif order_number:
        order = CustomerOrder.objects.filter(order_number=order_number).first()

    if not order:
        return JsonResponse({"success": False, "message": "Order not found."}, status=404)
    if order.status not in {"payment_pending", "confirmed"}:
        return JsonResponse(
            {
                "success": False,
                "message": "This order is not awaiting online payment confirmation.",
            },
            status=400,
        )

    try:
        order, bill, payment = finalize_order_after_payment(
            order,
            payment_reference=payment_reference,
            payment_method=payment_method,
        )
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=500)

    return JsonResponse(
        {
            "success": True,
            "message": f"Order {order.order_number} confirmed automatically after payment.",
            "order_id": order.id,
            "order_number": order.order_number,
            "bill_id": bill.id if bill else None,
            "invoice_number": bill.invoice_number if bill else "",
            "payment_id": payment.id if payment else None,
        }
    )
