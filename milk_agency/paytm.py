import json
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from paytmchecksum import PaytmChecksum

from customer_portal.models import CustomerOrder
from customer_portal.order_workflow import finalize_order_after_payment
from milk_agency.push_notifications import notify_admin_payment_recorded, notify_order_rejected

from .models import Bill, CustomerPayment


SUCCESS_PAYMENT_STATUSES = ("success", "SUCCESS")


def successful_payments_q():
    return Q(status__in=SUCCESS_PAYMENT_STATUSES)


def is_success_status(value):
    return str(value or "").strip().lower() == "success"


def _paytm_base_url():
    configured = getattr(settings, "PAYTM_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")

    website = str(getattr(settings, "PAYTM_WEBSITE", "") or "").upper()
    environment = str(getattr(settings, "PAYTM_ENV", "") or "").lower()
    if website == "WEBSTAGING" or environment == "staging":
        return "https://securestage.paytmpayments.com"
    return "https://securegw.paytm.in"


def _serialize_payload(payload):
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        return {"raw": payload}
    return {"raw": str(payload)}


def _extract_callback_payload(request):
    if request.POST:
        return request.POST.dict()

    if request.body:
        try:
            body = request.body.decode("utf-8")
            if body:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    return parsed
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
    return {}


def _verify_checksum(payload):
    checksum = payload.get("CHECKSUMHASH") or payload.get("signature")
    if not checksum:
        return False

    data = {key: value for key, value in payload.items() if key not in {"CHECKSUMHASH", "signature"}}
    return PaytmChecksum.verifySignature(data, settings.PAYTM_MERCHANT_KEY, checksum)


def _next_transaction_id(payment_order_id):
    return f"PENDING-{payment_order_id}"[:100]


def _update_bill_and_customer(payment):
    if payment.bill_id:
        total_paid = (
            CustomerPayment.objects.filter(bill_id=payment.bill_id)
            .filter(successful_payments_q())
            .aggregate(total=Sum("amount"))
        )["total"] or Decimal("0.00")
        payment.bill.last_paid = total_paid
        payment.bill.save(update_fields=["last_paid"])

    if payment.customer_id:
        payment.customer.due = payment.customer.get_actual_due()
        payment.customer.save(update_fields=["due"])


def _save_pending_payment(*, customer, amount, payment_order_id, bill=None, callback_payload=None):
    amount = Decimal(amount or 0)
    payment, created = CustomerPayment.objects.get_or_create(
        payment_order_id=payment_order_id,
        defaults={
            "customer": customer,
            "bill": bill,
            "amount": amount,
            "transaction_id": _next_transaction_id(payment_order_id),
            "method": "UPI",
            "status": "pending",
            "gateway": "PAYTM",
            "callback_payload": callback_payload or {},
        },
    )

    if not created:
        payment.customer = customer
        payment.bill = bill
        payment.amount = amount
        payment.method = payment.method or "UPI"
        payment.status = "pending" if not is_success_status(payment.status) else payment.status
        payment.gateway = "PAYTM"
        if callback_payload:
            payment.callback_payload = callback_payload
        payment.save(
            update_fields=[
                "customer",
                "bill",
                "amount",
                "method",
                "status",
                "gateway",
                "callback_payload",
            ]
        )
    return payment


def initiate_paytm_transaction(*, payment_order_id, amount, customer, callback_url=None):
    body = {
        "requestType": "Payment",
        "mid": settings.PAYTM_MID,
        "websiteName": settings.PAYTM_WEBSITE,
        "orderId": payment_order_id,
        "callbackUrl": callback_url or settings.PAYTM_CALLBACK_URL,
        "txnAmount": {
            "value": f"{Decimal(amount):.2f}",
            "currency": "INR",
        },
        "userInfo": {
            "custId": str(customer.id),
            "mobile": str(customer.phone or ""),
            "email": "",
        },
    }
    body_json = json.dumps(body, separators=(",", ":"))
    signature = PaytmChecksum.generateSignature(body_json, settings.PAYTM_MERCHANT_KEY)
    payload = {
        "body": body,
        "head": {
            "signature": signature,
        },
    }
    url = (
        f"{_paytm_base_url()}/theia/api/v1/initiateTransaction"
        f"?mid={settings.PAYTM_MID}&orderId={payment_order_id}"
    )

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    response_data = response.json()
    result = response_data.get("body", {})
    return {
        "success": bool(result.get("txnToken")),
        "payment_order_id": payment_order_id,
        "txnToken": result.get("txnToken", ""),
        "paytm_response": response_data,
    }


def initiate_paytm_payment(order_id, amount, customer_id):
    from .models import Customer

    customer = Customer.objects.get(pk=customer_id)
    result = initiate_paytm_transaction(
        payment_order_id=str(order_id),
        amount=amount,
        customer=customer,
    )
    return {
        "success": result["success"],
        "txnToken": result["txnToken"],
        "error": {} if result["success"] else result["paytm_response"],
    }


def initiate_order_transaction(order):
    grand_total = Decimal(order.total_amount or 0) + Decimal(order.delivery_charge or 0)
    payment_order_id = order.gateway_order_id or f"ORDER-{order.id}"
    payment = _save_pending_payment(
        customer=order.customer,
        amount=grand_total,
        payment_order_id=payment_order_id,
    )

    if order.gateway_order_id != payment_order_id or order.payment_status != "pending" or order.status != "payment_pending":
        order.gateway_order_id = payment_order_id
        order.payment_method = "PAYTM"
        order.payment_status = "pending"
        order.status = "payment_pending"
        order.save(update_fields=["gateway_order_id", "payment_method", "payment_status", "status", "updated_at"])

    init_result = initiate_paytm_transaction(
        payment_order_id=payment_order_id,
        amount=grand_total,
        customer=order.customer,
    )
    payment.callback_payload = _serialize_payload(init_result.get("paytm_response"))
    payment.save(update_fields=["callback_payload"])
    return {
        "payment": payment,
        "payment_order_id": payment_order_id,
        "amount": grand_total,
        **init_result,
    }


def latest_invoice_for_payment(customer):
    return (
        Bill.objects.filter(customer=customer, is_deleted=False)
        .order_by("-invoice_date", "-id")
        .first()
    )


def initiate_invoice_transaction(*, customer, amount):
    bill = latest_invoice_for_payment(customer)
    if not bill:
        raise ValueError("No invoice found for this customer.")

    payment_order_id = f"{bill.invoice_number}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"[:64]
    payment = _save_pending_payment(
        customer=customer,
        amount=amount,
        payment_order_id=payment_order_id,
        bill=bill,
    )
    init_result = initiate_paytm_transaction(
        payment_order_id=payment_order_id,
        amount=amount,
        customer=customer,
    )
    payment.callback_payload = _serialize_payload(init_result.get("paytm_response"))
    payment.save(update_fields=["callback_payload"])
    return {
        "payment": payment,
        "bill": bill,
        "payment_order_id": payment_order_id,
        "amount": Decimal(amount),
        **init_result,
    }


def _safe_transaction_id(payment, gateway_transaction_id):
    gateway_transaction_id = str(gateway_transaction_id or "").strip()
    if not gateway_transaction_id:
        return payment.transaction_id

    duplicate = (
        CustomerPayment.objects.exclude(pk=payment.pk)
        .filter(transaction_id=gateway_transaction_id)
        .exists()
    )
    if duplicate:
        return payment.transaction_id
    return gateway_transaction_id[:100]


def _mark_order_payment_failed(order, payment_reference):
    if order.status == "confirmed":
        return

    update_fields = ["payment_status", "status", "payment_method", "updated_at"]
    order.payment_status = "failed"
    order.status = "rejected"
    order.payment_method = order.payment_method or "PAYTM"
    if payment_reference:
        order.payment_reference = payment_reference
        update_fields.append("payment_reference")
    order.save(update_fields=update_fields)
    transaction.on_commit(
        lambda order_id=order.id: notify_order_rejected(
            CustomerOrder.objects.select_related("customer").get(pk=order_id)
        )
    )


def record_paytm_result(payload):
    payment_order_id = str(
        payload.get("ORDERID")
        or payload.get("orderId")
        or payload.get("payment_order_id")
        or ""
    ).strip()
    if not payment_order_id:
        raise ValueError("Missing payment order id.")

    gateway_transaction_id = str(
        payload.get("TXNID")
        or payload.get("txnId")
        or payload.get("gateway_transaction_id")
        or ""
    ).strip()
    status_value = str(
        payload.get("STATUS")
        or payload.get("status")
        or payload.get("resultStatus")
        or ""
    ).strip()
    status_lower = status_value.lower()
    is_success = status_value == "TXN_SUCCESS" or status_lower == "success"
    completed_status = "success" if is_success else "failed"

    with transaction.atomic():
        payment = (
            CustomerPayment.objects.select_for_update()
            .select_related("customer", "bill")
            .filter(payment_order_id=payment_order_id)
            .first()
        )
        if not payment:
            raise ValueError("Payment record not found for this order id.")

        linked_order = (
            CustomerOrder.objects.select_for_update()
            .filter(gateway_order_id=payment_order_id)
            .select_related("customer", "bill")
            .first()
        )

        payment.gateway = "PAYTM"
        payment.method = "UPI"
        payment.status = completed_status
        payment.gateway_transaction_id = gateway_transaction_id
        payment.transaction_id = _safe_transaction_id(payment, gateway_transaction_id)
        payment.callback_payload = payload
        payment.completed_at = timezone.now()

        if is_success:
            if linked_order:
                payment.transaction_id = _safe_transaction_id(payment, gateway_transaction_id)
                payment.gateway_transaction_id = gateway_transaction_id
                payment.callback_payload = payload
                payment.completed_at = timezone.now()
                payment.save(
                    update_fields=[
                        "transaction_id",
                        "gateway_transaction_id",
                        "callback_payload",
                        "completed_at",
                    ]
                )
                finalized_order, bill, _ = finalize_order_after_payment(
                    linked_order,
                    payment_reference=payment.transaction_id,
                    payment_method="PAYTM",
                    mark_paid=True,
                )
                payment.bill = bill
                payment.amount = Decimal(bill.total_amount or payment.amount or 0)
                payment.save(
                    update_fields=[
                        "gateway",
                        "method",
                        "status",
                        "gateway_transaction_id",
                        "transaction_id",
                        "callback_payload",
                        "completed_at",
                        "bill",
                        "amount",
                    ]
                )
                transaction.on_commit(
                    lambda payment_id=payment.id: notify_admin_payment_recorded(
                        CustomerPayment.objects.select_related("customer").get(pk=payment_id)
                    )
                )
                return {
                    "success": True,
                    "payment": payment,
                    "order": finalized_order,
                    "bill": bill,
                    "status": completed_status,
                }

            payment.save(
                update_fields=[
                    "gateway",
                    "method",
                    "status",
                    "gateway_transaction_id",
                    "transaction_id",
                    "callback_payload",
                    "completed_at",
                ]
            )
            _update_bill_and_customer(payment)
            transaction.on_commit(
                lambda payment_id=payment.id: notify_admin_payment_recorded(
                    CustomerPayment.objects.select_related("customer").get(pk=payment_id)
                )
            )
        else:
            payment.save(
                update_fields=[
                    "gateway",
                    "method",
                    "status",
                    "gateway_transaction_id",
                    "transaction_id",
                    "callback_payload",
                    "completed_at",
                ]
            )
            if linked_order:
                _mark_order_payment_failed(linked_order, payment.transaction_id)

        return {
            "success": is_success,
            "payment": payment,
            "order": linked_order,
            "bill": payment.bill,
            "status": completed_status,
        }


@csrf_exempt
def verify_paytm_callback(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method"}, status=405)

    payload = _extract_callback_payload(request)
    if not payload:
        return JsonResponse({"success": False, "message": "Empty callback payload"}, status=400)

    try:
        checksum_valid = _verify_checksum(payload)
    except Exception:
        checksum_valid = False

    if not checksum_valid:
        return JsonResponse({"success": False, "message": "Checksum mismatch"}, status=400)

    try:
        result = record_paytm_result(payload)
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)

    return JsonResponse(
        {
            "success": True,
            "payment_order_id": result["payment"].payment_order_id,
            "transaction_id": result["payment"].transaction_id,
            "status": result["status"],
        }
    )


def paytm_callback_redirect(request):
    response = verify_paytm_callback(request)
    if request.method == "POST" and response.status_code == 200:
        return redirect("customer_portal:collect_payment")
    return response
