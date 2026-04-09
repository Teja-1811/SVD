from rest_framework.decorators import api_view
from rest_framework.response import Response

from milk_agency.models import Item


@api_view(["GET"])
def categories_api(request):
    categories = (
        Item.objects.exclude(category__isnull=True)
        .exclude(category__exact="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
    result = [{"id": i + 1, "name": category} for i, category in enumerate(categories)]
    return Response({"categories": result})


@api_view(["GET"])
def products_api(request):
    category_id = request.GET.get("category_id")
    company_id = request.GET.get("company_id")

    if not category_id:
        return Response({"error": "category_id is required"}, status=400)

    categories = list(
        Item.objects.exclude(category__isnull=True)
        .exclude(category__exact="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )

    try:
        category_index = int(category_id) - 1
        category_name = categories[category_index]
    except Exception:
        return Response({"error": "Invalid category_id"}, status=400)

    items = Item.objects.filter(category=category_name, frozen=False).select_related("company")
    if company_id:
        items = items.filter(company_id=company_id)

    product_list = [
        {
            "id": item.id,
            "code": item.code,
            "name": item.name,
            "category": item.category,
            "company": item.company.name if item.company else "",
            "mrp": float(item.mrp),
            "selling_price": float(item.selling_price),
            "buying_price": float(item.buying_price),
            "margin": float(item.selling_price - item.buying_price),
            "stock": item.stock_quantity,
            "image": item.image.url if item.image else "",
            "pcs_count": item.pcs_count,
            "description": item.description or "",
        }
        for item in items
    ]

    return Response(
        {
            "category_id": int(category_id),
            "category_name": category_name,
            "count": len(product_list),
            "products": product_list,
        }
    )
