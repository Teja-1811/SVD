from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Sum
from milk_agency.models import Customer, Bill, Item


# =======================================================
# CUSTOMER DASHBOARD API
# =======================================================
@api_view(["GET"])
def customer_dashboard_api(request):
    user_id = request.GET.get("user_id")

    if not user_id:
        return Response({"error": "user_id is required"}, status=400)

    try:
        customer = Customer.objects.get(id=user_id)
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=404)

    # Balance
    balance = customer.due or 0

    data = {
        "customerName": customer.name,
        "balance": float(balance),
        "shopName": customer.shop_name or "",
        "phone": customer.phone,
        "accountStatus": "Active" if customer.is_active else "Inactive",
    }

    return Response(data, status=200)


# =======================================================
# CUSTOMER ITEMS API
# =======================================================

@api_view(["GET"])
def categories_api(request):
    # Extract all unique categories from Items
    categories = (
        Item.objects.exclude(category__isnull=True)
                    .exclude(category__exact="")
                    .values_list("category", flat=True)
                    .distinct()
    )

    result = []
    for i, cat in enumerate(categories):
        result.append({
            "id": i + 1,
            "name": cat
        })

    return Response(result)

@api_view(["GET"])
def customer_items_api(request):
    # Get all non-frozen items
    items = Item.objects.filter(frozen=False).order_by("name")

    item_list = []

    for item in items:
        margin_percent = 0

        try:
            margin_percent = ((item.selling_price - item.buying_price) / item.buying_price) * 100
        except:
            margin_percent = 0

        item_list.append({
            "id": item.id,
            "name": item.name,
            "mrp": float(item.mrp),
            "sellingPrice": float(item.selling_price),
            "buyingPrice": float(item.buying_price),
            "marginPercent": round(margin_percent, 2),
            "image": item.image.url if item.image else None,
            "category": item.category or "Others"
        })

    return Response({"items": item_list}, status=200)
