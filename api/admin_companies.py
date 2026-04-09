from django.http import JsonResponse
from django.db.models import Count, Sum, F, DecimalField, ExpressionWrapper, Value, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view

from milk_agency.models import Company, Item


def _absolute_media_url(request, file_field):
    if not file_field:
        return None

    try:
        url = file_field.url
    except Exception:
        return None

    return request.build_absolute_uri(url)


# ==========================================================
# 1️⃣ LIST COMPANIES (DASHBOARD DATA)
# ==========================================================

@api_view(["GET"])
def companies_list_api(request):

    companies = Company.objects.all().order_by("name")

    data = []
    for c in companies:
        item_stats = Item.objects.filter(company=c).aggregate(
            total_items=Count("id"),
            active_items=Count("id", filter=Q(frozen=False)),
            total_qty=Coalesce(Sum("stock_quantity"), Value(0)),
            total_value=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("stock_quantity") * F("buying_price"),
                        output_field=DecimalField(max_digits=14, decimal_places=2),
                    )
                ),
                Value(0),
            ),
            low_stock_items=Count("id", filter=Q(stock_quantity__lte=5)),
        )

        data.append({
            "id": c.id,
            "name": c.name,
            "logo": _absolute_media_url(request, c.logo),
            "website_link": c.website_link,
            "total_items": item_stats["total_items"] or 0,
            "active_items": item_stats["active_items"] or 0,
            "total_qty": float(item_stats["total_qty"] or 0),
            "total_value": float(item_stats["total_value"] or 0),
            "low_stock_items": item_stats["low_stock_items"] or 0,
        })

    return JsonResponse({
        "count": len(data),
        "companies": data
    })


# ==========================================================
# 2️⃣ ADD COMPANY
# ==========================================================

@api_view(["POST"])
def add_company_api(request):
    """
    Android sends (multipart/form-data):
    - name (text)
    - website_link (text)
    - logo (file, optional)
    """

    name = request.data.get("name")
    website_link = request.data.get("website_link", "")
    logo = request.FILES.get("logo")

    if not name:
        return JsonResponse({"status": "error", "message": "Company name is required"}, status=400)

    company = Company.objects.create(
        name=name,
        website_link=website_link,
        logo=logo if logo else None
    )

    return JsonResponse({
        "status": "success",
        "company_id": company.id,
        "message": "Company added successfully"
    })


# ==========================================================
# 3️⃣ EDIT / UPDATE COMPANY
# ==========================================================

@api_view(["POST"])
def edit_company_api(request, company_id):
    """
    Android sends (multipart/form-data):
    - name
    - website_link
    - logo (optional)
    """

    company = get_object_or_404(Company, id=company_id)

    name = request.data.get("name")
    website_link = request.data.get("website_link", company.website_link)
    logo = request.FILES.get("logo")

    if name:
        company.name = name

    company.website_link = website_link

    if logo:
        company.logo = logo

    company.save()

    return JsonResponse({
        "status": "success",
        "company_id": company.id,
        "message": "Company updated successfully"
    })


# Catalog API for selected companies only (for dropdowns, etc.)
@api_view(["GET"])
def company_items_api(request, company_id):
    items = Item.objects.filter(
        company_id=company_id,
        frozen=False
    ).values("id", "code", "name", "category", "buying_price", "selling_price", "mrp", "stock_quantity", "pcs_count")

    return JsonResponse(list(items), safe=False)

