import json
import os
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from urllib import error, parse, request

from django.conf import settings
from django.urls import reverse


class _PaytmChecksumAdapter:
    def __init__(self, generate_signature, verify_signature):
        self.generateSignature = generate_signature
        self.verifySignature = verify_signature


PAYTM_IMPORT_ERROR = ""


try:
    from paytmchecksum import generateSignature, verifySignature
    PaytmChecksum = _PaytmChecksumAdapter(generateSignature, verifySignature)
except Exception as exc:  # pragma: no cover - depends on deployment environment
    PAYTM_IMPORT_ERROR = str(exc)
    try:
        import paytmchecksum as paytmchecksum_module  # type: ignore
        PaytmChecksum = _PaytmChecksumAdapter(
            paytmchecksum_module.generateSignature,
            paytmchecksum_module.verifySignature,
        )
    except Exception as exc:  # pragma: no cover - depends on deployment environment
        PAYTM_IMPORT_ERROR = str(exc)
        try:
            import PaytmChecksum as PaytmChecksum  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on deployment environment
            PAYTM_IMPORT_ERROR = str(exc)
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
        missing.append("paytmchecksum import")
    if missing:
        detail = f" ({PAYTM_IMPORT_ERROR})" if PAYTM_IMPORT_ERROR and PaytmChecksum is None else ""
        raise PaytmConfigError("Paytm is not configured yet. Missing: " + ", ".join(missing) + detail)
    return config


def get_paytm_diagnostics(request=None, *, callback_url_name=None, callback_kwargs=None):
    environment = _env("PAYTM_ENV", "staging").lower() or "staging"
    if environment not in {"staging", "production"}:
        environment = "staging"

    diagnostics = {
        "package_loaded": PaytmChecksum is not None,
        "mid_present": bool(_env("PAYTM_MID")),
        "merchant_key_present": bool(_env("PAYTM_MERCHANT_KEY")),
        "website": _env("PAYTM_WEBSITE", "DEFAULT" if environment == "production" else "WEBSTAGING") or "-",
        "environment": environment,
        "base_url": "https://securegw.paytm.in" if environment == "production" else "https://securegw-stage.paytm.in",
        "callback_url": "",
        "import_error": PAYTM_IMPORT_ERROR,
    }
    if request and callback_url_name:
        diagnostics["callback_url"] = build_callback_url(
            request,
            callback_url_name,
            kwargs=callback_kwargs,
        )
    return diagnostics


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


def build_callback_url(request, url_name="users:paytm_callback", *, kwargs=None):
    url = request.build_absolute_uri(reverse(url_name, kwargs=kwargs))
    parsed = parse.urlsplit(url)
    environment = _env("PAYTM_ENV", "staging").lower()
    host = (parsed.hostname or "").lower()

    # Production Paytm callbacks should always use HTTPS on public hosts,
    # even when Django sits behind a proxy that forwards the original scheme.
    if environment == "production" and host not in {"localhost", "127.0.0.1"} and parsed.scheme != "https":
        url = parse.urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment))
    return url


def initiate_paytm_checkout(request, *, gateway_order_id, amount, customer=None, callback_url=None):
    config = get_paytm_config()
    callback_url = callback_url or build_callback_url(request)
    body = {
        "requestType": "Payment",
        "mid": config.mid,
        "websiteName": config.website,
        "orderId": gateway_order_id,
        "callbackUrl": callback_url,
        "txnAmount": {
            "value": _normalized_amount(amount),
            "currency": "INR",
        },
        "userInfo": {
            "custId": str(getattr(customer, "id", "") or ""),
            "mobile": getattr(customer, "phone", "") or "",
            "email": getattr(customer, "email", "") or "",
            "firstName": getattr(customer, "name", "") or "",
        },
    }
    signature = _generate_signature(body, config.merchant_key)
    payload = {
        "body": body,
        "head": {"signature": signature},
    }
    query = parse.urlencode({"mid": config.mid, "orderId": gateway_order_id})
    response = _call_paytm_api(f"{config.initiate_transaction_url}?{query}", payload)
    result_info = response.get("body", {}).get("resultInfo", {})
    result_status = str(result_info.get("resultStatus") or "").strip()
    result_code = str(result_info.get("resultCode") or "").strip()
    txn_token = str(response.get("body", {}).get("txnToken") or "").strip()
    if result_code not in {"0000", "0002", "00000900"} or not txn_token:
        message = result_info.get("resultMsg") or "Could not start Paytm payment."
        status_prefix = f"{result_status} " if result_status else ""
        code_prefix = f"{result_code}: " if result_code else ""
        raise PaytmGatewayError(f"Paytm {status_prefix}{code_prefix}{message}".strip())
    return {
        "mid": config.mid,
        "order_id": gateway_order_id,
        "txn_token": txn_token,
        "amount": _normalized_amount(amount),
        "callback_url": callback_url,
        "gateway_url": f"{config.show_payment_page_url}?{query}",
    }


def initiate_paytm_transaction(request, order, *, amount):
    return initiate_paytm_checkout(
        request,
        gateway_order_id=getattr(order, "gateway_order_id", "") or order.order_number,
        amount=amount,
        customer=order.customer,
        callback_url=build_callback_url(request, "users:paytm_callback"),
    )


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
