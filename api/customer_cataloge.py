from collections import OrderedDict

from rest_framework.decorators import api_view
from rest_framework.response import Response

from milk_agency.models import Item


@api_view(["GET"])
def customer_cataloge_api(request):
    """
    Returns category-wise product catalog for Android app.
    Optional query params:
    - company_id: filter catalog by company
    - include_empty: true/false (include categories without products, default false)
    """
    company_id = request.GET.get("company_id")
    include_empty = str(request.GET.get("include_empty", "false")).lower() == "true"

    items_qs = Item.objects.filter(frozen=False).select_related("company").order_by("category", "name")
    if company_id:
        items_qs = items_qs.filter(company_id=company_id)

    catalog_map = OrderedDict()

    for item in items_qs:
        category_name = (item.category or "").strip()
        if not category_name:
            continue

        if category_name not in catalog_map:
            catalog_map[category_name] = {
                "category_name": category_name,
                "products": [],
            }

        catalog_map[category_name]["products"].append(
            {
                "id": item.id,
                "name": item.name,
                "company": item.company.name if item.company else "",
                "mrp": float(item.mrp),
                "selling_price": float(item.selling_price),
                "buying_price": float(item.buying_price),
                "margin": float(item.selling_price - item.buying_price),
                "stock": item.stock_quantity,
                "pcs_count": item.pcs_count,
                "image": item.image.url if item.image else "",
                "description": item.description or "",
            }
        )

    catalog = []
    for idx, category_data in enumerate(catalog_map.values(), start=1):
        if not include_empty and not category_data["products"]:
            continue

        catalog.append(
            {
                "category_id": idx,
                "category_name": category_data["category_name"],
                "products_count": len(category_data["products"]),
                "products": category_data["products"],
            }
        )

    return Response(
        {
            "status": "success",
            "categories_count": len(catalog),
            "catalog": catalog,
        }
    )
