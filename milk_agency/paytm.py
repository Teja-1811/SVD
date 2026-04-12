import json
import time
from decimal import Decimal

import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from paytmchecksum import PaytmChecksum


# ============================================
# BASE URL
# ============================================

def _paytm_base_url():
    if settings.PAYTM_ENV == "staging":
        return "https://securegw-stage.paytm.in"
    return "https://securegw.paytm.in"


# ============================================
# CALLBACK URL
# ============================================

def build_paytm_callback_url(request):
    return request.build_absolute_uri(reverse("users_paytm_callback"))


# ============================================
# VERIFY TRANSACTION (MANDATORY)
# ============================================

def verify_transaction(order_id):
    url = f"{_paytm_base_url()}/v3/order/status"

    body = {
        "mid": settings.PAYTM_MID,
        "orderId": order_id
    }

    checksum = PaytmChecksum.generateSignature(
        json.dumps(body),
        settings.PAYTM_MERCHANT_KEY
    )

    payload = {
        "body": body,
        "head": {"signature": checksum}
    }

    response = requests.post(url, json=payload)
    return response.json()


# ============================================
# INITIATE TRANSACTION
# ============================================

def initiate_paytm_transaction(order_id, amount, customer, request):

    # ✅ Unique order ID
    payment_order_id = f"ORD{order_id}{int(time.time())}"

    body = {
        "requestType": "Payment",
        "mid": settings.PAYTM_MID,
        "websiteName": settings.PAYTM_WEBSITE,
        "industryTypeId": settings.PAYTM_INDUSTRY_TYPE_ID,
        "channelId": "WEB",
        "orderId": payment_order_id,
        "callbackUrl": build_paytm_callback_url(request),
        "txnAmount": {
            "value": f"{Decimal(amount):.2f}",
            "currency": "INR",
        },
        "userInfo": {
            "custId": str(customer.id),
            "mobile": customer.phone if customer.phone else "7777777777",
            "email": customer.email if customer.email else "test@paytm.com",
        },
    }

    body_json = json.dumps(body, separators=(",", ":"))

    checksum = PaytmChecksum.generateSignature(
        body_json,
        settings.PAYTM_MERCHANT_KEY
    )

    payload = {
        "body": body,
        "head": {"signature": checksum}
    }

    url = f"{_paytm_base_url()}/theia/api/v1/initiateTransaction?mid={settings.PAYTM_MID}&orderId={payment_order_id}"

    response = requests.post(url, json=payload)
    response_data = response.json()

    print("PAYTM INIT RESPONSE:", response_data)

    txn_token = response_data.get("body", {}).get("txnToken")

    return {
        "order_id": payment_order_id,
        "txnToken": txn_token,
        "response": response_data
    }


# ============================================
# CHECKSUM VERIFY
# ============================================

def verify_checksum(payload):
    checksum = payload.get("CHECKSUMHASH")

    data = {k: v for k, v in payload.items() if k != "CHECKSUMHASH"}

    return PaytmChecksum.verifySignature(
        data,
        settings.PAYTM_MERCHANT_KEY,
        checksum
    )


# ============================================
# CALLBACK
# ============================================

@csrf_exempt
def paytm_callback(request):

    payload = request.POST.dict()

    print("CALLBACK DATA:", payload)

    # Step 1: checksum verify
    if not verify_checksum(payload):
        return JsonResponse({"status": "checksum failed"})

    order_id = payload.get("ORDERID")

    # Step 2: server verification
    verify_res = verify_transaction(order_id)

    print("VERIFY RESPONSE:", verify_res)

    status = verify_res.get("body", {}).get("resultInfo", {}).get("resultStatus")

    if status == "TXN_SUCCESS":
        print("PAYMENT SUCCESS")
        # 👉 update your order/payment here
    else:
        print("PAYMENT FAILED")

    return redirect("users:orders")