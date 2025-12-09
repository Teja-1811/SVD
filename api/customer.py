from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Sum
from milk_agency.models import Customer, Bill


@api_view(["GET"])
def customer_dashboard_api(request):
    user_id = request.GET.get("user_id")

    if not user_id:
        return Response({"error": "user_id is required"}, status=400)

    try:
        customer = Customer.objects.get(id=user_id)
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=404)


    balance = customer.due

    # ==========================
    # BUILD RESPONSE
    # ==========================
    data = {
        "customerName": customer.name,
        "balance": float(balance),
        "shopName": customer.shop_name,
        "phone": customer.phone,
        "accountStatus": "Active" if customer.is_active else "Inactive",
    }

    return Response(data, status=200)
