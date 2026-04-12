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
    return "https://securegw-stage.paytm.in" if settings.PAYTM_ENV == "staging" else "https://securegw.paytm.in"


# ============================================
# CALLBACK URL
# ============================================

def build_paytm_callback_url(request):
    return request.build_absolute_uri(reverse("milk_agency:users_paytm_callback"))


# ============================================
# VERIFY TRANSACTION
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

    # ✅ UNIQUE ORDER ID (VERY IMPORTANT)
    payment_order_id = f"ORD{order_id}{int(time.time())}"

    body = {
        "requestType": "Payment",
        "mid": settings.PAYTM_MID,
        "websiteName": settings.PAYTM_WEBSITE,
        "orderId": payment_order_id,
        "callbackUrl": build_paytm_callback_url(request),
        "txnAmount": {
            "value": f"{Decimal(amount):.2f}",
            "currency": "INR",
        },
        "userInfo": {
            "custId": str(customer.id),
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

    response = requests.post(
        url,
        data=json.dumps(payload, separators=(",", ":")),
        headers={"Content-Type": "application/json"}
    )

    response_data = response.json()

    print("=== PAYTM DEBUG ===")
    print(json.dumps(response_data, indent=2))
    print("===================")

    txn_token = response_data.get("body", {}).get("txnToken")

    if not txn_token:
        return {
            "error": True,
            "response": response_data
        }

    return {
        "error": False,
        "order_id": payment_order_id,
        "txnToken": txn_token
    }


# ============================================
# START PAYMENT API (🔥 THIS IS WHAT FRONTEND CALLS)
# ============================================

@csrf_exempt
def start_payment(request):
    try:
        data = json.loads(request.body)
        amount = data.get("amount")

        if not amount:
            return JsonResponse({"error": "Invalid amount"}, status=400)

        customer = request.user  # adjust if needed
        order_id = f"PMT{int(time.time())}"

        result = initiate_paytm_transaction(order_id, amount, customer, request)

        if result.get("error"):
            return JsonResponse({
                "error": "Paytm failed",
                "details": result.get("response")
            }, status=500)

        # ✅ FINAL RESPONSE (IMPORTANT)
        return JsonResponse({
            "order_id": result["order_id"],
            "txnToken": result["txnToken"],
            "mid": settings.PAYTM_MID,   # 🔥 REQUIRED
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================
# CALLBACK
# ============================================

@csrf_exempt
def paytm_callback(request):

    payload = request.POST.dict()
    print("CALLBACK:", payload)

    checksum = payload.get("CHECKSUMHASH")

    data = {k: v for k, v in payload.items() if k != "CHECKSUMHASH"}

    if not PaytmChecksum.verifySignature(data, settings.PAYTM_MERCHANT_KEY, checksum):
        return JsonResponse({"status": "checksum failed"})

    order_id = payload.get("ORDERID")

    verify_res = verify_transaction(order_id)
    print("VERIFY:", verify_res)

    status = verify_res.get("body", {}).get("resultInfo", {}).get("resultStatus")

    if status == "TXN_SUCCESS":
        print("PAYMENT SUCCESS")
        # update DB here
    else:
        print("PAYMENT FAILED")

    return redirect("users:orders")