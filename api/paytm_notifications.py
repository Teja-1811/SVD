import json

from django.db.models import Q

from customer_portal.models import CustomerOrder
from customer_portal.order_workflow import finalize_order_after_payment
from api.paytm import PaytmConfigError, PaytmGatewayError, fetch_transaction_status, verify_callback_checksum


def _apply_failed_payment_state(order):
    update_fields = ["payment_status", "updated_at"]
    if order.payment_status != "failed":
        order.payment_status = "failed"
    if order.status not in {"cancelled", "rejected", "confirmed"}:
        order.status = "payment_pending"
        update_fields.append("status")
    order.save(update_fields=update_fields)


def extract_paytm_params(request):
    if request.method != "POST":
        return {}
    if request.POST:
        return request.POST.dict()
    try:
        payload = json.loads(request.body or "{}")
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def process_paytm_notification(params):
    payment_order_id = str(params.get("ORDERID") or params.get("orderId") or "").strip()
    txn_id = str(params.get("TXNID") or params.get("txnId") or "").strip()

    if not payment_order_id:
        return {
            "success": False,
            "code": 400,
            "message": "Paytm notification did not include an order reference.",
        }

    order = (
        CustomerOrder.objects.filter(Q(order_number=payment_order_id) | Q(gateway_order_id=payment_order_id))
        .select_related("customer")
        .first()
    )
    if not order:
        return {
            "success": False,
            "code": 404,
            "message": f"Order {payment_order_id} was not found.",
        }

    try:
        checksum_valid = verify_callback_checksum(params)
    except PaytmConfigError as exc:
        return {"success": False, "code": 500, "message": str(exc), "order": order}

    try:
        status_response = fetch_transaction_status(order.gateway_order_id or payment_order_id or order.order_number)
    except (PaytmConfigError, PaytmGatewayError) as exc:
        return {
            "success": False,
            "code": 502,
            "message": f"Could not verify the Paytm payment yet: {exc}",
            "order": order,
        }

    status_body = status_response.get("body", {})
    result_info = status_body.get("resultInfo", {})
    result_status = str(result_info.get("resultStatus") or status_body.get("STATUS") or "").strip()
    result_code = str(result_info.get("resultCode") or "").strip()
    txn_status = str(
        status_body.get("resultStatus")
        or status_body.get("STATUS")
        or result_info.get("resultStatus")
        or result_info.get("resultCode")
        or ""
    ).strip().upper()
    pay_mode = str(status_body.get("paymentMode") or status_body.get("PAYMENTMODE") or "PAYTM").strip() or "PAYTM"
    verified_txn_id = str(status_body.get("txnId") or status_body.get("TXNID") or txn_id or "").strip()
    result_message = str(
        result_info.get("resultMsg")
        or status_body.get("RESPMSG")
        or "Payment status received from Paytm."
    ).strip()

    if txn_status in {"TXN_SUCCESS", "SUCCESS", "01"}:
        try:
            finalize_order_after_payment(
                order,
                payment_reference=verified_txn_id or order.order_number,
                payment_method=pay_mode,
            )
        except Exception as exc:
            return {
                "success": False,
                "code": 500,
                "message": f"Payment was received, but order confirmation failed: {exc}",
                "order": order,
            }

        return {
            "success": True,
            "code": 200,
            "message": (
                f"Payment received successfully for {order.order_number}."
                if checksum_valid
                else f"Payment verified with Paytm for {order.order_number}."
            ),
            "order": order,
        }

    _apply_failed_payment_state(order)
    resp_msg = str(params.get("RESPMSG", "") or result_message or "").lower()
    if "cancel" in resp_msg:
        message = "Payment cancelled by user"
    elif "fail" in resp_msg or "failure" in resp_msg:
        message = "Payment failed"
    else:
        message = f"Payment not completed (Paytm: {result_message or 'Unknown status'})"
    return {
        "success": False,
        "code": 400,
        "message": message,
        "order": order,
    }
