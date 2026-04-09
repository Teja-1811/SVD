import json
import os
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from urllib import error, parse, request

from django.conf import settings
from django.urls import reverse


try:
    import paytmchecksum as PaytmChecksum
except ImportError:  # pragma: no cover - depends on deployment environment
    try:
        import PaytmChecksum  # type: ignore
    except ImportError:  # pragma: no cover - depends on deployment environment
        PaytmChecksum = None


class PaytmConfigError(Exception):
    pass


class PaytmGatewayError(Exception):
    pass


@dataclass(frozen=True)
class PaytmConfig:
    mid: str
    merchant_key: str
    website: str
    environment: str

    @property
    def base_url(self):
        return "https://securegw.paytm.in" if self.environment == "production" else "https://securegw-stage.paytm.in"

    @property
    def initiate_transaction_url(self):
        return f"{self.base_url}/theia/api/v1/initiateTransaction"

    @property
    def show_payment_page_url(self):
        return f"{self.base_url}/theia/api/v1/showPaymentPage"

    @property
    def transaction_status_url(self):
        return f"{self.base_url}/v3/order/status"


def _env(name, default=""):
    return (os.environ.get(name) or getattr(settings, name, default) or "").strip()


def get_paytm_config():
    environment = _env("PAYTM_ENV", "staging").lower()
    if environment not in {"staging", "production"}:
        environment = "staging"

    website_default = "DEFAULT" if environment == "production" else "WEBSTAGING"
    config = PaytmConfig(
        mid=_env("PAYTM_MID"),
        merchant_key=_env("PAYTM_MERCHANT_KEY"),
        website=_env("PAYTM_WEBSITE", website_default),
        environment=environment,
    )

    missing = []
    if not config.mid:
        missing.append("PAYTM_MID")
    if not config.merchant_key:
        missing.append("PAYTM_MERCHANT_KEY")
    if PaytmChecksum is None:
        missing.append("paytmchecksum package")
    if missing:
        raise PaytmConfigError("Paytm is not configured yet. Missing: " + ", ".join(missing))
    return config


def _json_body(payload):
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _generate_signature(payload, merchant_key):
    body = _json_body(payload)
    return PaytmChecksum.generateSignature(body, merchant_key)


def _call_paytm_api(url, payload):
    data = _json_body(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PaytmGatewayError(f"Paytm request failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise PaytmGatewayError(f"Could not reach Paytm: {exc.reason}") from exc


def _normalized_amount(value):
    return str(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_callback_url(request):
    return request.build_absolute_uri(reverse("users:paytm_callback"))


def initiate_paytm_transaction(request, order, *, amount):
    config = get_paytm_config()
    callback_url = build_callback_url(request)
    body = {
        "requestType": "Payment",
        "mid": config.mid,
        "websiteName": config.website,
        "orderId": order.order_number,
        "callbackUrl": callback_url,
        "txnAmount": {
            "value": _normalized_amount(amount),
            "currency": "INR",
        },
        "userInfo": {
            "custId": str(order.customer_id),
            "mobile": getattr(order.customer, "phone", "") or "",
            "email": getattr(order.customer, "email", "") or "",
            "firstName": getattr(order.customer, "name", "") or "",
        },
    }
    signature = _generate_signature(body, config.merchant_key)
    payload = {
        "body": body,
        "head": {"signature": signature},
    }
    query = parse.urlencode({"mid": config.mid, "orderId": order.order_number})
    response = _call_paytm_api(f"{config.initiate_transaction_url}?{query}", payload)
    result_info = response.get("body", {}).get("resultInfo", {})
    result_code = str(result_info.get("resultCode") or "").strip()
    txn_token = str(response.get("body", {}).get("txnToken") or "").strip()
    if result_code not in {"0000", "0002", "00000900"} or not txn_token:
        message = result_info.get("resultMsg") or "Could not start Paytm payment."
        raise PaytmGatewayError(str(message))
    return {
        "mid": config.mid,
        "order_id": order.order_number,
        "txn_token": txn_token,
        "amount": _normalized_amount(amount),
        "callback_url": callback_url,
        "gateway_url": f"{config.show_payment_page_url}?{query}",
    }


def verify_callback_checksum(params):
    config = get_paytm_config()
    checksum = str(params.get("CHECKSUMHASH") or "").strip()
    if not checksum:
        return False
    payload = {key: value for key, value in params.items() if key != "CHECKSUMHASH"}
    return bool(PaytmChecksum.verifySignature(payload, config.merchant_key, checksum))


def fetch_transaction_status(order_number):
    config = get_paytm_config()
    body = {
        "mid": config.mid,
        "orderId": order_number,
    }
    signature = _generate_signature(body, config.merchant_key)
    payload = {
        "body": body,
        "head": {"signature": signature},
    }
    return _call_paytm_api(config.transaction_status_url, payload)
