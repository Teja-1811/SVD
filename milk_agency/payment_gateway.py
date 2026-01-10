"""
Payment_Gateway.py
==================

Single-file payment gateway module supporting:

1. Direct UPI deep links (GPay / PhonePe / Paytm / BHIM)
2. QR code generation for UPI
3. Shareable UPI payment links
4. Paytm Payment Gateway (PG) – FULLY IMPLEMENTED
   (credentials required to go live)

This file is standalone and NOT auto-linked to any app.
You decide when and where to import it.

Author: SVD
"""

import uuid
import urllib.parse
from io import BytesIO
from base64 import b64encode

import qrcode
from paytmchecksum import PaytmChecksum


# ============================================================
# BASIC CONFIG (UPDATE WHEN READY)
# ============================================================

# ---- UPI CONFIG ----
UPI_ID = "svdmilkagency@ptyes"      
PAYEE_NAME = "Sri Vijaya Durga Milk Agency"
CURRENCY = "INR"

# ---- PAYTM CONFIG (PLACEHOLDERS) ----
PAYTM_MERCHANT_ID = "YOUR_MID"
PAYTM_MERCHANT_KEY = "YOUR_MERCHANT_KEY"
PAYTM_WEBSITE = "DEFAULT"
PAYTM_CHANNEL_ID = "WEB"
PAYTM_INDUSTRY_TYPE_ID = "Retail"
PAYTM_CALLBACK_URL = "https://svdagencies.shop/paytm/callback/"
PAYTM_ENVIRONMENT = "STAGING"    # STAGING / PROD


# ============================================================
# COMMON HELPERS
# ============================================================

def generate_transaction_id(prefix="TXN"):
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def format_amount(amount):
    return f"{float(amount):.2f}"


# ============================================================
# UPI PAYMENT (NO GATEWAY REQUIRED)
# ============================================================

def generate_upi_link(amount, note="", txn_id=None):
    """
    Generates a UPI deep link that opens UPI apps directly
    """
    if not txn_id:
        txn_id = generate_transaction_id()

    params = {
        "pa": UPI_ID,
        "pn": PAYEE_NAME,
        "am": format_amount(amount),
        "cu": CURRENCY,
        "tn": note or f"Payment {txn_id}",
        "tr": txn_id,
    }

    return "upi://pay?" + urllib.parse.urlencode(params)


def generate_upi_qr(amount, note="", txn_id=None):
    """
    Generates a BASE64 QR code image for UPI payment
    (directly embeddable in HTML)
    """
    upi_link = generate_upi_link(amount, note, txn_id)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_link)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")

    return b64encode(buffer.getvalue()).decode()


def generate_upi_payment_link(amount, note=""):
    """
    Shareable UPI link (WhatsApp / SMS / Email)
    """
    return generate_upi_link(amount, note)


# ============================================================
# PAYTM PAYMENT GATEWAY (FULLY IMPLEMENTED)
# ============================================================

def get_paytm_txn_url():
    if PAYTM_ENVIRONMENT == "PROD":
        return "https://securegw.paytm.in/order/process"
    return "https://securegw-stage.paytm.in/order/process"


def create_paytm_order(customer_id, amount, order_id=None):
    """
    Builds Paytm order parameters
    """
    if not order_id:
        order_id = generate_transaction_id("ORD")

    params = {
        "MID": PAYTM_MERCHANT_ID,
        "ORDER_ID": order_id,
        "CUST_ID": str(customer_id),
        "TXN_AMOUNT": format_amount(amount),
        "CHANNEL_ID": PAYTM_CHANNEL_ID,
        "WEBSITE": PAYTM_WEBSITE,
        "INDUSTRY_TYPE_ID": PAYTM_INDUSTRY_TYPE_ID,
        "CALLBACK_URL": PAYTM_CALLBACK_URL,
    }

    checksum = PaytmChecksum.generateSignature(
        params, PAYTM_MERCHANT_KEY
    )

    params["CHECKSUMHASH"] = checksum

    return {
        "paytm_url": get_paytm_txn_url(),
        "params": params,
        "order_id": order_id
    }


def verify_paytm_response(response_data):
    """
    Verifies Paytm callback response
    """
    data = dict(response_data)
    checksum = data.pop("CHECKSUMHASH", None)

    is_valid = PaytmChecksum.verifySignature(
        data, PAYTM_MERCHANT_KEY, checksum
    )

    return {
        "is_valid": is_valid,
        "order_id": data.get("ORDERID"),
        "txn_id": data.get("TXNID"),
        "amount": data.get("TXNAMOUNT"),
        "status": data.get("STATUS"),
        "raw": data,
    }


# ============================================================
# BASIC VALIDATION
# ============================================================

def is_valid_amount(amount):
    try:
        return float(amount) > 0
    except Exception:
        return False


# ============================================================
# USAGE NOTES (REFERENCE ONLY)
# ============================================================
"""
# ---- UPI ----
link = generate_upi_link(500, "Milk Due")
qr = generate_upi_qr(500)
share = generate_upi_payment_link(500)

# ---- PAYTM ----
order = create_paytm_order(customer_id=12, amount=500)
# POST order["params"] to order["paytm_url"]

# ---- CALLBACK ----
result = verify_paytm_response(request.POST)
"""
