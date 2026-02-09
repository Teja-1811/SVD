from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from decimal import Decimal, InvalidOperation
from django.db import transaction
import uuid
from milk_agency.models import Customer, CustomerPayment, Bill


# =========================
# CUSTOMER LIST
# =========================
@api_view(['GET'])
def api_customer_list(request):

    customers = Customer.objects.filter(
        is_superuser=False,
        is_staff=False
    ).order_by('id')

    data = []

    for index, c in enumerate(customers, start=1):
        data.append({
            "id": c.id,
            "serial_no": index,
            "name": c.name,
            "shop_name": c.shop_name or "",
            "phone": c.phone or "",
            "due": float(c.due or 0),
            "frozen": c.frozen
        })

    return Response({"customers": data})


# =========================
# CUSTOMER DETAIL
# =========================
@api_view(['GET'])
def api_customer_detail(request, pk):

    c = get_object_or_404(Customer, id=pk, is_superuser=False)

    return Response({
        "id": c.id,
        "name": c.name,
        "shop_name": c.shop_name or "",
        "phone": c.phone or "",
        "due": float(c.due or 0),
        "city": c.city,
        "state": c.state,
        "frozen": c.frozen,
        "retailer_id": c.retailer_id
    })


# =========================
# FREEZE / UNFREEZE
# =========================
@api_view(['POST'])
def api_toggle_freeze(request, pk):

    c = get_object_or_404(Customer, id=pk, is_superuser=False)

    c.frozen = not c.frozen
    c.save()

    return Response({
        "success": True,
        "frozen": c.frozen
    })


# =========================
# UPDATE BALANCE
# =========================
@api_view(['POST'])
def api_update_balance(request, pk):

    customer = get_object_or_404(Customer, id=pk, is_superuser=False)

    amount = request.data.get("amount")

    if amount is None:
        return Response({"success": False, "message": "Amount is required"}, status=400)

    try:
        amount = Decimal(str(amount))
    except InvalidOperation:
        return Response({"success": False, "message": "Invalid amount"}, status=400)

    # Get latest bill (not just current month)
    latest_bill = Bill.objects.filter(
        customer=customer
    ).order_by('-invoice_date', '-id').first()

    transaction_id = f"PAY-{uuid.uuid4().hex[:10].upper()}"

    with transaction.atomic():
        # Update latest invoice last_paid
        if latest_bill:
            latest_bill.last_paid += amount
            latest_bill.save()

        # Update customer due balance
        customer.due -= amount
        customer.save()

        # Create payment record
        CustomerPayment.objects.create(
            customer=customer,
            amount=amount,
            transaction_id=transaction_id,
            method="Cash",
            status="Completed"
        )

    return Response({
        "success": True,
        "message": f"Payment of ₹{float(amount):.2f} recorded successfully",
        "new_balance": float(customer.due),
        "last_paid_updated": latest_bill.id if latest_bill else None
    })


#--------------------------
# Add and Edit Customer API
#--------------------------
@api_view(['POST'])
def api_add_edit_customer(request):
    customer_id = request.data.get("customer_id")
    name = request.data.get("name")
    shop_name = request.data.get("shop_name", "")
    phone = request.data.get("phone", "")
    city = request.data.get("city", "")
    state = request.data.get("state", "")
    retailer_id = request.data.get("retailer_id", "")

    if not name:
        return Response({"success": False, "message": "Name is required"}, status=400)

    if customer_id:
        # Edit existing customer
        customer = get_object_or_404(Customer, id=customer_id, is_superuser=False)
        customer.name = name
        customer.shop_name = shop_name
        customer.phone = phone
        customer.city = city
        customer.state = state
        customer.retailer_id = retailer_id
        customer.save()
        message = "Customer updated successfully"
    else:
        # Add new customer
        Customer.objects.create(
            name=name,
            shop_name=shop_name,
            phone=phone,
            city=city,
            state=state,
            retailer_id=retailer_id
        )
        message = "Customer added successfully"

    return Response({"success": True, "message": message})