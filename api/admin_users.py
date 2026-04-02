from decimal import Decimal, InvalidOperation
import uuid

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from milk_agency.models import Bill, Customer, CustomerPayment


def _user_queryset():
    return Customer.objects.filter(
        is_superuser=False,
        is_staff=False,
        user_type="user",
    ).order_by("id")


@api_view(["GET"])
def api_user_list(request):
    users = _user_queryset()
    data = []
    for index, user in enumerate(users, start=1):
        data.append(
            {
                "id": user.id,
                "serial_no": index,
                "name": user.name,
                "shop_name": user.shop_name or "",
                "phone": user.phone or "",
                "due": float(user.get_actual_due() or 0),
                "frozen": user.frozen,
                "retailer_id": user.retailer_id or "",
                "area": user.area or "",
            }
        )
    return Response({"users": data}, status=200)


@api_view(["GET"])
def api_user_detail(request, pk):
    user = get_object_or_404(_user_queryset(), pk=pk)
    return Response(
        {
            "id": user.id,
            "name": user.name,
            "shop_name": user.shop_name or "",
            "phone": user.phone or "",
            "due": float(user.get_actual_due() or 0),
            "city": user.city,
            "state": user.state,
            "area": user.area,
            "frozen": user.frozen,
            "retailer_id": user.retailer_id or "",
        },
        status=200,
    )


@api_view(["POST"])
def api_toggle_user_freeze(request, pk):
    user = get_object_or_404(_user_queryset(), pk=pk)
    user.frozen = not user.frozen
    user.save(update_fields=["frozen"])
    return Response({"success": True, "frozen": user.frozen}, status=200)


@api_view(["POST"])
def api_update_user_balance(request, pk):
    user = get_object_or_404(_user_queryset(), pk=pk)
    amount = request.data.get("amount")

    if amount is None:
        return Response({"success": False, "message": "Amount is required"}, status=400)

    try:
        amount = Decimal(str(amount))
    except InvalidOperation:
        return Response({"success": False, "message": "Invalid amount"}, status=400)

    if amount <= 0:
        return Response({"success": False, "message": "Amount must be greater than zero"}, status=400)

    if user.frozen:
        return Response({"success": False, "message": "User is frozen. Payment not allowed."}, status=400)

    latest_bill = Bill.objects.filter(customer=user, is_deleted=False).order_by("-invoice_date", "-id").first()
    transaction_id = f"PAY-{uuid.uuid4().hex[:10].upper()}"

    with transaction.atomic():
        CustomerPayment.objects.create(
            customer=user,
            bill=latest_bill,
            amount=amount,
            transaction_id=transaction_id,
            method="Cash",
            status="SUCCESS",
        )

        if latest_bill:
            latest_bill.last_paid += amount
            latest_bill.save(update_fields=["last_paid"])

        user.due = user.get_actual_due()
        user.save(update_fields=["due"])

    return Response(
        {
            "success": True,
            "message": f"Payment of {float(amount):.2f} recorded successfully",
            "new_balance": float(user.get_actual_due()),
            "last_paid_updated": latest_bill.id if latest_bill else None,
        },
        status=200,
    )


@api_view(["POST"])
def api_add_edit_user(request):
    user_id = request.data.get("user_id") or request.data.get("customer_id")
    name = request.data.get("name")
    shop_name = request.data.get("shop_name", "")
    phone = request.data.get("phone", "")
    city = request.data.get("city", "")
    state = request.data.get("state", "")
    retailer_id = request.data.get("retailer_id", "")
    area = request.data.get("area", "")

    if not name:
        return Response({"success": False, "message": "Name is required"}, status=400)

    if user_id:
        user = get_object_or_404(_user_queryset(), pk=user_id)
        user.name = name
        user.shop_name = shop_name
        user.phone = phone
        user.city = city
        user.state = state
        user.area = area
        user.retailer_id = retailer_id
        user.save()
        message = "User updated successfully"
    else:
        user = Customer.objects.create(
            name=name,
            shop_name=shop_name,
            phone=phone,
            city=city,
            state=state,
            area=area,
            retailer_id=retailer_id,
            user_type="user",
            password=phone or "123456",
        )
        message = "User added successfully"

    return Response({"success": True, "message": message, "id": user.id}, status=200)
