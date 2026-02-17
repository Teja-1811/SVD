from rest_framework.decorators import api_view
from rest_framework.response import Response
from milk_agency.models import Customer


# =======================================================
# CUSTOMER DASHBOARD API
# =======================================================
@api_view(["GET"])
def customer_dashboard_api(request):
    user_id = request.GET.get("user_id")

    # ---- Validate user_id ----
    if not user_id:
        return Response({"error": "user_id is required"}, status=400)

    try:
        customer = Customer.objects.get(id=int(user_id))
    except (Customer.DoesNotExist, ValueError):
        return Response({"error": "Customer not found"}, status=404)

    # ---- Accurate ledger-based balance ----
    balance = customer.get_actual_due()

    data = {
        "customerName": customer.name,
        "balance": float(balance),
        "shopName": customer.shop_name or "",
        "phone": customer.phone,
        "accountStatus": "Active" if customer.is_active else "Inactive",
    }

    return Response(data, status=200)
