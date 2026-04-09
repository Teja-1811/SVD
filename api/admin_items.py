from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Count, Sum, Value
from django.db.models.functions import Coalesce
from milk_agency.models import Item


def _absolute_media_url(request, file_field):
    if not file_field:
        return None

    try:
        url = file_field.url
    except Exception:
        return None

    return request.build_absolute_uri(url)


# -------------------------
# 1️⃣ GET ALL CATEGORIES
# -------------------------
@api_view(['GET'])
def get_categories(request):

    categories = list(
        Item.objects
        .exclude(category__isnull=True)
        .exclude(category__exact="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )

    summary = list(
        Item.objects
        .exclude(category__isnull=True)
        .exclude(category__exact="")
        .values("category")
        .annotate(
            total_items=Count("id"),
            total_stock=Coalesce(Sum("stock_quantity"), Value(0)),
        )
        .order_by("category")
    )

    return Response({
        "categories": categories,
        "summary": summary,
    })


# -------------------------
# 2️⃣ GET ITEMS BY CATEGORY
# -------------------------
@api_view(['GET'])
def get_items_by_category(request):

    category = request.GET.get("category")

    if not category:
        return Response({"error": "category parameter is required"}, status=400)

    items = Item.objects.filter(category=category).select_related("company")

    data = [
        {
            "id": item.id,
            "code": item.code,
            "name": item.name,
            "company": item.company.name if item.company else None,
            "company_logo": _absolute_media_url(request, item.company.logo) if item.company else None,
            "category": item.category,
            "selling_price": str(item.selling_price),
            "buying_price": str(item.buying_price),
            "mrp": str(item.mrp),
            "stock_quantity": item.stock_quantity,
            "pcs_count": item.pcs_count,
            "description": item.description or "",
            "image": _absolute_media_url(request, item.image),
            "frozen": item.frozen,
            "stock_value": float((item.stock_quantity or 0) * (item.buying_price or 0)),
        }
        for item in items
    ]

    return Response({
        "category": category,
        "count": len(data),
        "items": data,
    })


# -------------------------
# 3️⃣ ADD ITEM
# -------------------------
@api_view(['POST'])
def add_item(request):

    code = request.data.get("code")
    name = request.data.get("name")
    company_id = request.data.get("company_id")
    category = request.data.get("category")
    selling_price = request.data.get("selling_price", 0)
    buying_price = request.data.get("buying_price", 0)
    mrp = request.data.get("mrp", 0)
    stock_quantity = request.data.get("stock_quantity", 0)
    pcs_count = request.data.get("pcs_count", 1)
    image = request.FILES.get("image")

    if not name:
        return Response({"error": "name is required"}, status=400)

    if code and Item.objects.filter(code=code).exists():
        return Response({"error": "Item code already exists"}, status=400)

    item = Item.objects.create(
        code=code,
        name=name,
        company_id=company_id or None,
        category=category,
        selling_price=selling_price or 0,
        buying_price=buying_price or 0,
        mrp=mrp or 0,
        stock_quantity=stock_quantity or 0,
        pcs_count=pcs_count or 1,
        image=image,
        description=request.data.get("description", ""),
    )

    return Response({
        "success": True,
        "message": "Item created successfully",
        "id": item.id
    })


# -------------------------
# 4️⃣ EDIT ITEM
# -------------------------
@api_view(['POST'])
def edit_item(request, item_id):

    try:
        item = Item.objects.get(id=item_id)
    except Item.DoesNotExist:
        return Response({"error": "Item not found"}, status=404)

    item.code = request.data.get("code", item.code)
    item.name = request.data.get("name", item.name)
    company_id = request.data.get("company_id")
    if company_id:
        item.company_id = int(company_id)
    item.category = request.data.get("category", item.category)
    item.selling_price = request.data.get("selling_price", item.selling_price)
    item.buying_price = request.data.get("buying_price", item.buying_price)
    item.mrp = request.data.get("mrp", item.mrp)
    item.stock_quantity = request.data.get("stock_quantity", item.stock_quantity)
    item.pcs_count = request.data.get("pcs_count", item.pcs_count)
    item.description = request.data.get("description", item.description)

    image = request.FILES.get("image")
    if image:
        item.image = image

    item.save()

    return Response({
        "success": True,
        "message": "Item updated successfully",
        "item_id": item.id,
    })

#-------------------------
#feeze/unfreeze item
#-------------------------
@api_view(['POST'])
def toggle_freeze_item(request, item_id):

    try:
        item = Item.objects.get(id=item_id)
    except Item.DoesNotExist:
        return Response({"error": "Item not found"}, status=404)

    item.frozen = not item.frozen
    item.save()

    status = "frozen" if item.frozen else "unfrozen"
    return Response({
        "success": True,
        "message": f"Item {status} successfully",
        "frozen": item.frozen,
    })
