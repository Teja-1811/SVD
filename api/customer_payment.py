from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from milk_agency.models import Bill, Customer, CustomerPayment
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
            status="SUCCESS",
        )

        customer.due = customer.get_actual_due()
        customer.save()
        transaction.on_commit(lambda payment_id=payment.id: notify_admin_payment_recorded(CustomerPayment.objects.select_related("customer").get(pk=payment_id)))

    return Response(
        {"status": "success", "payment_id": payment.id, "new_balance": str(customer.get_actual_due())},
        status=status.HTTP_200_OK,
    )
