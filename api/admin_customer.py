from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from decimal import Decimal, InvalidOperation

from milk_agency.models import Customer


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

    c = get_object_or_404(Customer, id=pk, is_superuser=False)

    amount = request.data.get("amount")

    if amount is None:
        return Response({"success": False, "message": "amount required"}, status=400)

    try:
        amount = Decimal(amount)
    except InvalidOperation:
        return Response({"success": False, "message": "invalid amount"}, status=400)

    c.due -= amount
    c.save()

    return Response({
        "success": True,
        "new_balance": float(c.due)
    })
