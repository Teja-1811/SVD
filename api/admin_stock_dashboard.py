from datetime import datetime, timedelta

from django.http import JsonResponse
from django.db.models import Sum, F, FloatField, ExpressionWrapper, Value
from django.db.models.functions import Coalesce
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import transaction
from milk_agency.models import Item, BillItem, StockInEntry, LeakageEntry
from milk_agency.utils import apply_stock_updates, delete_stock_entry, parse_decimal, update_stock_entry


# ==========================================================
#  STOCK DASHBOARD DATA API  (FOR ANDROID)
# ==========================================================

@api_view(["GET"])
def stock_dashboard_api(request):
    today = datetime.today().date()
    try:
        selected_date = datetime.strptime(request.GET.get("date", str(today)), "%Y-%m-%d").date()
    except ValueError:
        selected_date = today

    try:
        month = int(request.GET.get("month", today.month))
        year = int(request.GET.get("year", today.year))
    except ValueError:
        return Response({"error": "Invalid month or year"}, status=400)

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
        "selling_price",
        category_name=F("category"),
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

    # -------- STOCK IN / OUT LAST 30 DAYS ----------
    thirty_days_ago = datetime.today() - timedelta(days=30)
    stock_in = StockInEntry.objects.filter(
        date__gte=thirty_days_ago.date()
    ).aggregate(
        total=Coalesce(Sum("quantity"), Value(0.0), output_field=FloatField())
    )["total"]

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

    date_entries = list(
        StockInEntry.objects.filter(date=selected_date)
        .select_related("item", "company")
        .order_by("-created_at", "-id")
        .values(
            "id",
            "date",
            "created_at",
            "crates",
            "quantity",
            "value",
            item_name=F("item__name"),
            company_name=F("company__name"),
        )
    )

    leakage_qs = LeakageEntry.objects.filter(
        date__year=year,
        date__month=month
    ).select_related("item", "item__company").order_by("-date", "-created_at")

    monthly_loss = leakage_qs.aggregate(
        total=Coalesce(Sum("total_loss"), Value(0.0), output_field=FloatField())
    )["total"]

    return Response({
        "summary": {
            "total_items": total_items,
            "total_stock_value": float(total_stock_value or 0),
            "low_stock_count": low_stock_count,
            "stock_in_30d": float(stock_in or 0),
            "stock_out_30d": float(stock_out or 0),
            "monthly_loss": float(monthly_loss or 0),
        },
        "selected_date": str(selected_date),
        "month": month,
        "year": year,
        "date_entries": [
            {
                **entry,
                "date": str(entry["date"]),
                "created_at": entry["created_at"].strftime("%Y-%m-%d %H:%M:%S") if entry["created_at"] else None,
            }
            for entry in date_entries
        ],
        "leakage_entries": [
            {
                "id": entry.id,
                "date": str(entry.date),
                "item_id": entry.item_id,
                "item_name": entry.item.name if entry.item else None,
                "company_name": entry.item.company.name if entry.item and entry.item.company else None,
                "quantity": entry.quantity,
                "unit_cost": float(entry.unit_cost),
                "total_loss": float(entry.total_loss),
                "notes": entry.notes,
            }
            for entry in leakage_qs
        ],
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

    items = request.data.get("updates", request.data.get("items", []))
    print("Received stock update:", items)
    stock_updates = []
    entry_date = request.data.get("entry_date")
    try:
        entry_date_value = datetime.strptime(entry_date, "%Y-%m-%d").date() if entry_date else None
    except ValueError:
        return Response({"status": "error", "message": "Invalid entry_date"}, status=400)

    for entry in items:
        try:
            item = Item.objects.get(id=entry["id"])
            crates = float(entry.get("crates", 0))
            discount = float(entry.get("discount", 0) or 0)
            stock_updates.append({
                "item": item,
                "crates": crates,
                "discount": discount,
            })

        except Item.DoesNotExist:
            continue

    updated = apply_stock_updates(stock_updates, entry_date=entry_date_value)

    return Response({
        "status": "success",
        "updated_items": updated
    })


@api_view(["POST"])
def save_leakage_api(request):
    item_id = request.data.get("item")
    quantity = request.data.get("quantity")
    date_value = request.data.get("date")
    notes = request.data.get("notes", "")

    if not item_id or not quantity:
        return Response({"success": False, "message": "item and quantity are required"}, status=400)

    try:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return Response({"success": False, "message": "quantity must be greater than 0"}, status=400)

    try:
        leakage_date = datetime.strptime(date_value, "%Y-%m-%d").date() if date_value else datetime.today().date()
    except ValueError:
        return Response({"success": False, "message": "Invalid date"}, status=400)

    with transaction.atomic():
        item = Item.objects.select_for_update().filter(id=item_id, frozen=False).first()
        if not item:
            return Response({"success": False, "message": "Item not found"}, status=404)

        if item.stock_quantity < quantity:
            return Response(
                {"success": False, "message": f"Leakage quantity exceeds available stock ({item.stock_quantity})"},
                status=400,
            )

        item.stock_quantity -= quantity
        item.save(update_fields=["stock_quantity"])

        leakage = LeakageEntry.objects.create(
            item=item,
            date=leakage_date,
            quantity=quantity,
            unit_cost=item.buying_price,
            notes=notes,
        )

    return Response({
        "success": True,
        "message": "Leakage recorded successfully",
        "entry": {
            "id": leakage.id,
            "date": str(leakage.date),
            "item_id": item.id,
            "item_name": item.name,
            "quantity": leakage.quantity,
            "unit_cost": float(leakage.unit_cost),
            "total_loss": float(leakage.total_loss),
            "notes": leakage.notes,
            "stock_quantity": item.stock_quantity,
        },
    })


@api_view(["DELETE", "POST"])
def delete_leakage_api(request, leakage_id):
    leakage = LeakageEntry.objects.select_related("item").filter(id=leakage_id).first()
    if not leakage:
        return Response({"success": False, "message": "Leakage entry not found"}, status=404)

    with transaction.atomic():
        item = Item.objects.select_for_update().get(id=leakage.item_id)
        item.stock_quantity += leakage.quantity
        item.save(update_fields=["stock_quantity"])
        leakage.delete()

    return Response({"success": True, "message": "Leakage deleted and stock restored"})


@api_view(["PUT", "PATCH"])
def edit_stock_entry_api(request, entry_id):
    entry = StockInEntry.objects.select_related("item", "company").filter(id=entry_id).first()
    if not entry:
        return Response({"success": False, "message": "Stock entry not found"}, status=404)

    crates = parse_decimal(request.data.get("crates"))
    discount = parse_decimal(request.data.get("discount"))
    date_raw = request.data.get("entry_date") or request.data.get("date")

    if crates <= 0:
        return Response({"success": False, "message": "Crates must be greater than zero"}, status=400)

    try:
        selected_date = datetime.strptime(date_raw, "%Y-%m-%d").date() if date_raw else entry.date
    except ValueError:
        return Response({"success": False, "message": "Invalid entry date"}, status=400)

    updated_entry = update_stock_entry(entry, crates=crates, discount=discount, date_value=selected_date)
    return Response(
        {
            "success": True,
            "message": "Stock entry updated successfully",
            "entry": {
                "id": updated_entry.id,
                "date": str(updated_entry.date),
                "crates": float(updated_entry.crates),
                "quantity": float(updated_entry.quantity),
                "value": float(updated_entry.value),
                "item_id": updated_entry.item_id,
                "item_name": updated_entry.item.name,
                "company_name": updated_entry.company.name if updated_entry.company else None,
            },
            "item_stock_quantity": updated_entry.item.stock_quantity,
        }
    )


@api_view(["DELETE", "POST"])
def delete_stock_entry_api(request, entry_id):
    entry = StockInEntry.objects.select_related("item", "company").filter(id=entry_id).first()
    if not entry:
        return Response({"success": False, "message": "Stock entry not found"}, status=404)

    item = entry.item
    delete_stock_entry(entry)
    return Response(
        {
            "success": True,
            "message": "Stock entry deleted successfully",
            "item_stock_quantity": item.stock_quantity,
        }
    )
