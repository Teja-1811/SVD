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

    customer = request.user  # ✅ Correct (Customer is auth user)

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

        # Lock row properly inside transaction
        customer = Customer.objects.select_for_update().get(pk=customer.pk)

        if CustomerPayment.objects.filter(transaction_id=txn_id).exists():
            return Response(
                {"error": "Duplicate transaction"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save payment first (source of truth)
        CustomerPayment.objects.create(
            customer=customer,
            amount=amount,
            transaction_id=txn_id,
            method="UPI",
            status="SUCCESS"
        )

        # Recalculate due using accounting logic
        customer.due = customer.get_actual_due()
        customer.save()

    return Response(
        {
            "status": "success",
            "new_balance": str(customer.due)  # ✅ correct field
        },
        status=status.HTTP_200_OK
    )
