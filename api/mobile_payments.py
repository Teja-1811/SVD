from decimal import Decimal

from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.order_creator import create_or_replace_order
from api.paytm import (
    PaytmConfigError,
    PaytmGatewayError,
    fetch_transaction_status,
    initiate_paytm_transaction,
)
from customer_portal.models import CustomerOrder


def _grand_total(order):
    return Decimal(order.total_amount or 0) + Decimal(order.delivery_charge or 0)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_prepare_payment_order(request):
    items = request.data.get("items", [])
    delivery_date = request.data.get("delivery_date")
    payment_method = str(request.data.get("payment_method") or "PAYTM").strip().upper() or "PAYTM"

    try:
        order = create_or_replace_order(
            customer=request.user,
            items=items,
            delivery_date_str=delivery_date,
            initial_status="payment_pending" if payment_method != "COD" else "pending",
            payment_method=payment_method,
        )
    except ValueError as exc:
        return Response({"success": False, "message": str(exc)}, status=400)
    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=500)

    total = _grand_total(order)

    if payment_method == "PAYTM":
        try:
            checkout = initiate_paytm_transaction(request, order, amount=total)
        except (PaytmConfigError, PaytmGatewayError) as exc:
            return Response({"success": False, "message": str(exc)}, status=400)

        return Response(
            {
                "success": True,
                "order_id": order.id,
                "order_number": order.order_number,
                "delivery_date": str(order.delivery_date),
                "status": order.status,
                "items_total": float(order.total_amount or 0),
                "delivery_charge": float(order.delivery_charge or 0),
                "grand_total": float(total),
                "payment_method": payment_method,
                "paytm": checkout,
            }
        )

    return Response(
        {
            "success": True,
            "order_id": order.id,
            "order_number": order.order_number,
            "delivery_date": str(order.delivery_date),
            "status": order.status,
            "items_total": float(order.total_amount or 0),
            "delivery_charge": float(order.delivery_charge or 0),
            "grand_total": float(total),
            "payment_method": payment_method,
        }
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mobile_payment_status(request, order_id):
    order = CustomerOrder.objects.filter(id=order_id, customer=request.user).first()
    if not order:
        return Response({"success": False, "message": "Order not found."}, status=404)

    try:
        paytm_status = fetch_transaction_status(order.order_number)
    except (PaytmConfigError, PaytmGatewayError) as exc:
        return Response({"success": False, "message": str(exc)}, status=400)

    body = paytm_status.get("body", {})
    result_info = body.get("resultInfo", {})

    return Response(
        {
            "success": True,
            "order_id": order.id,
            "order_number": order.order_number,
            "order_status": order.status,
            "payment_status": order.payment_status,
            "payment_reference": order.payment_reference,
            "gateway_status": {
                "result_code": result_info.get("resultCode"),
                "result_status": result_info.get("resultStatus"),
                "result_message": result_info.get("resultMsg"),
                "txn_id": body.get("txnId"),
                "bank_txn_id": body.get("bankTxnId"),
                "txn_amount": body.get("txnAmount"),
                "txn_date": body.get("txnDate"),
            },
            "checked_at": timezone.now().isoformat(),
        }
    )
