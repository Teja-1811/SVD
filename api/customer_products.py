from rest_framework.decorators import api_view
from rest_framework.response import Response
from milk_agency.models import  Item

# =======================================================
# CUSTOMER ITEMS API
# =======================================================
@api_view(["GET"])
def categories_api(request):
    categories = (
        Item.objects.exclude(category__isnull=True)
                    .exclude(category__exact="")
                    .values_list("category", flat=True)
                    .distinct()
    )

    result = [{"id": i + 1, "name": cat} for i, cat in enumerate(categories)]
    return Response(result)


@api_view(["GET"])
def products_api(request):
    category_id = request.GET.get("category_id")

    if not category_id:
        return Response({"error": "category_id is required"}, status=400)

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

    items = Item.objects.filter(category=category_name, freeze=False)

    product_list = [
        {
            "id": item.id,
            "name": item.name,
            "company": item.company.name if item.company else "",
            "mrp": float(item.mrp),
            "selling_price": float(item.selling_price),
            "margin": float(item.selling_price - item.buying_price),
            "stock": item.stock_quantity,
            "image": item.image.url if item.image else "",
            "pcs_count": item.pcs_count,
        }
        for item in items
    ]

    return Response(product_list)


