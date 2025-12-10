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
def products_api(request):
    category_id = request.GET.get("category_id")

    if not category_id:
        return Response({"error": "category_id is required"}, status=400)

    # Convert category_id back to category name
    categories = (
        Item.objects.exclude(category__isnull=True)
                    .exclude(category__exact="")
                    .values_list("category", flat=True)
                    .distinct()
    )

    try:
        category_index = int(category_id) - 1
        category_name = list(categories)[category_index]
    except:
        return Response({"error": "Invalid category_id"}, status=400)

    # Fetch items belonging to this category
    items = Item.objects.filter(category=category_name)

    product_list = []
    for item in items:
        product_list.append({
            "id": item.id,
            "name": item.name,
            "mrp": float(item.mrp),
            "selling_price": float(item.selling_price),
            "margin": float(item.selling_price - item.buying_price),
            "stock": item.stock_quantity,
            "image": item.image.url if item.image else ""
        })

    return Response(product_list)
