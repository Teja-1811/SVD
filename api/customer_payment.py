from decimal import Decimal, InvalidOperation
from django.db import transaction
from milk_agency.models import Customer, CustomerPayment
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def record_customer_payment(request):
    try:
        customer = Customer.objects.select_for_update().get(user=request.user)
    except Customer.DoesNotExist:
        return Response(
            {"error": "Customer not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    # ---------- VALIDATE INPUT ----------
    try:
        amount = Decimal(request.data.get("amount"))
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, TypeError):
        return Response(
            {"error": "Invalid amount"},
            status=status.HTTP_400_BAD_REQUEST
        )

    txn_id = request.data.get("transaction_id")
    if not txn_id:
        return Response(
            {"error": "Transaction ID required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ---------- ATOMIC PAYMENT ----------
    with transaction.atomic():

        if CustomerPayment.objects.filter(transaction_id=txn_id).exists():
            return Response(
                {"error": "Duplicate transaction"},
                status=status.HTTP_400_BAD_REQUEST
            )

        CustomerPayment.objects.create(
            customer=customer,
            amount=amount,
            transaction_id=txn_id,
            method="UPI",
            status="SUCCESS"
        )

        # Update customer balance
        customer.due -= amount
        customer.save()

    return Response(
        {
            "status": "success",
            "new_balance": str(customer.balance)
        },
        status=status.HTTP_200_OK
    )
