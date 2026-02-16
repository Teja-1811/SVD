from datetime import datetime, timedelta

from django.http import JsonResponse
from django.db.models import Sum, F, FloatField, ExpressionWrapper, Value
from django.db.models.functions import Coalesce
from rest_framework.decorators import api_view
from rest_framework.response import Response
from milk_agency.models import Item, BillItem


# ==========================================================
#  STOCK DASHBOARD DATA API  (FOR ANDROID)
# ==========================================================

@api_view(["GET"])
def stock_dashboard_api(request):

    # -------- SUMMARY ----------
    total_items = Item.objects.count()

    total_stock_value = Item.objects.annotate(
        value=ExpressionWrapper(
            F("stock_quantity") * F("selling_price"),
            output_field=FloatField()
        )
    ).aggregate(
        total=Coalesce(Sum("value"), Value(0.0), output_field=FloatField())
    )["total"]

    low_stock_count = Item.objects.filter(stock_quantity__lte=5).count()

    # -------- ALL ITEMS ----------
    all_items_qs = Item.objects.select_related("company").values(
        "id",
        "name",
        "stock_quantity",
        "pcs_count",
        company_name=F("company__name"),
    )

    all_items = list(all_items_qs)

    # -------- TOP 10 ITEMS BY STOCK VALUE ----------
    top_items_qs = Item.objects.annotate(
        stock_value=ExpressionWrapper(
            F("stock_quantity") * F("selling_price"),
            output_field=FloatField()
        )
    ).order_by("-stock_value").values(
        "id",
        "name",
        "stock_quantity",
        "selling_price",
        "stock_value",
        company_name=F("company__name"),
    )[:10]

    top_items = list(top_items_qs)

    # -------- STOCK OUT LAST 30 DAYS ----------
    thirty_days_ago = datetime.today() - timedelta(days=30)

    stock_out = BillItem.objects.filter(
        bill__invoice_date__gte=thirty_days_ago
    ).aggregate(
        total=Coalesce(Sum("quantity"), Value(0.0), output_field=FloatField())
    )["total"]

    # -------- COMPANY-WISE STOCK VALUE ----------
    company_data_qs = Item.objects.values(
        company_name=F("company__name")
    ).annotate(
        total_value=Sum(
            ExpressionWrapper(
                F("stock_quantity") * F("selling_price"),
                output_field=FloatField()
            )
        )
    ).order_by("-total_value")

    company_data = list(company_data_qs)

    return Response({
        "summary": {
            "total_items": total_items,
            "total_stock_value": float(total_stock_value or 0),
            "low_stock_count": low_stock_count,
            "stock_in_30d": 0,
            "stock_out_30d": float(stock_out or 0),
        },
        "all_items": all_items,
        "top_items": top_items,
        "company_data": company_data,
    })


# ==========================================================
#  UPDATE STOCK API  (FOR ANDROID)
# ==========================================================

@api_view(["POST"])
def update_stock_api(request):
    """
    Android will send:
    {
      "items": [
        {"id": 1, "crates": 2},
        {"id": 5, "crates": 1}
      ]
    }
    """

    items = request.data.get("items", [])
    print("Received stock update:", items)
    updated = []

    for entry in items:
        try:
            item = Item.objects.get(id=entry["id"])
            crates = float(entry.get("crates", 0))

            old_qty = item.stock_quantity
            pcs = item.pcs_count if item.pcs_count > 0 else 1

            added_qty = crates * pcs
            item.stock_quantity += added_qty
            item.save()

            updated.append({
                "id": item.id,
                "name": item.name,
                "old_quantity": old_qty,
                "new_quantity": item.stock_quantity,
                "added_quantity": added_qty
            })

        except Item.DoesNotExist:
            continue

    return Response({
        "status": "success",
        "updated_items": updated
    })
