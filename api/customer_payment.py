from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from milk_agency.models import Bill, Customer, CustomerPayment
from milk_agency.paytm import (
    initiate_invoice_transaction,
    is_success_status,
    record_paytm_result,
)
from milk_agency.push_notifications import notify_admin_payment_recorded


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def record_customer_payment(request):
    customer = request.user

    try:
        amount = Decimal(request.data.get("amount"))
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, TypeError):
        return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

    txn_id = request.data.get("transaction_id")
    bill_id = request.data.get("bill_id")
    method = request.data.get("method", "PAYTM")

    if not txn_id:
        return Response({"error": "Transaction ID required"}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        customer = Customer.objects.select_for_update().get(pk=customer.pk)

        if CustomerPayment.objects.filter(transaction_id=txn_id).exists():
            return Response({"error": "Duplicate transaction"}, status=status.HTTP_400_BAD_REQUEST)

        bill = None
        if bill_id:
            bill = Bill.objects.filter(id=bill_id, customer=customer, is_deleted=False).first()

        payment = CustomerPayment.objects.create(
            customer=customer,
            bill=bill,
            amount=amount,
            transaction_id=txn_id,
            method=method,
            status="success",
        )

        customer.due = customer.get_actual_due()
        customer.save()
        transaction.on_commit(lambda payment_id=payment.id: notify_admin_payment_recorded(CustomerPayment.objects.select_related("customer").get(pk=payment_id)))

    return Response(
        {"status": "success", "payment_id": payment.id, "new_balance": str(customer.get_actual_due())},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def initiate_customer_gateway_payment(request):
    customer = request.user
    raw_amount = request.data.get("amount")

    try:
        amount = Decimal(raw_amount)
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, TypeError):
        return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = initiate_invoice_transaction(customer=customer, amount=amount, request=request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"error": f"Unable to initiate payment: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

    return Response(
        {
            "success": True,
            "gateway": "PAYTM",
            "payment_order_id": result["payment_order_id"],
            "invoice_number": result["bill"].invoice_number,
            "bill_id": result["bill"].id,
            "amount": float(result["amount"]),
            "txnToken": result["txnToken"],
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def paytm_payment_result_api(request):
    payment_order_id = str(request.data.get("payment_order_id") or "").strip()
    if not payment_order_id:
        return Response({"error": "payment_order_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    payment = (
        CustomerPayment.objects.select_related("customer", "bill")
        .filter(payment_order_id=payment_order_id, customer=request.user)
        .first()
    )
    if not payment:
        return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

    gateway_status = str(request.data.get("status") or "").strip()
    gateway_transaction_id = str(request.data.get("transaction_id") or "").strip()

    if gateway_status:
        try:
            result = record_paytm_result(
                {
                    "ORDERID": payment_order_id,
                    "STATUS": gateway_status,
                    "TXNID": gateway_transaction_id,
                    "RESPMSG": request.data.get("message", ""),
                }
            )
            payment = result["payment"]
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    payment.refresh_from_db()

    return Response(
        {
            "success": True,
            "payment_order_id": payment.payment_order_id,
            "transaction_id": payment.transaction_id,
            "gateway_transaction_id": payment.gateway_transaction_id,
            "status": payment.status,
            "bill_id": payment.bill_id,
            "is_success": is_success_status(payment.status),
        },
        status=status.HTTP_200_OK,
    )
