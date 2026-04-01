from collections import OrderedDict
from datetime import datetime, timedelta
from itertools import groupby

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, FloatField, ExpressionWrapper, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.utils import timezone

from .models import Item, BillItem, Company, StockInEntry
from .utils import apply_stock_updates, parse_decimal, update_stock_entry, delete_stock_entry


def _parse_entry_date(raw_value):
    if raw_value:
        try:
            return datetime.strptime(raw_value, "%Y-%m-%d").date()
        except ValueError:
            pass
    return timezone.localdate()


def _group_stock_items():
    items = Item.objects.filter(frozen=False).select_related("company").order_by("category", "name")

    grouped_items = {}
    for category, group in groupby(items, key=lambda x: (x.category or "others").lower()):
        grouped_items[category] = sorted(list(group), key=lambda x: x.name.lower())

    category_order = ["milk", "curd", "cups", "buckets", "panner", "sweets", "flavoured milk", "ghee", "others"]
    ordered_grouped = OrderedDict()
    for category in category_order:
        ordered_grouped[category] = grouped_items.get(category, [])

    for category, category_items in grouped_items.items():
        if category not in ordered_grouped:
            ordered_grouped[category] = category_items

    return ordered_grouped


def _build_stock_context(selected_date):
    grouped_items = _group_stock_items()
    companies = list(
        Company.objects.filter(items__frozen=False)
        .distinct()
        .values_list("name", flat=True)
    )

    entries = (
        StockInEntry.objects.filter(date=selected_date)
        .select_related("item", "company")
        .order_by("-created_at", "-id")
    )

    company_totals = (
        StockInEntry.objects.filter(date=selected_date, company__isnull=False)
        .values("company_id", "company__name")
        .annotate(
            total_value=Coalesce(Sum("value"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
            total_crates=Coalesce(Sum("crates"), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)),
            total_quantity=Coalesce(Sum("quantity"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)),
        )
        .order_by("company__name")
    )

    grand_total = entries.aggregate(
        total=Coalesce(Sum("value"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))
    )["total"]

    return {
        "grouped_items": grouped_items,
        "companies": companies,
        "selected_date": selected_date,
        "entries": entries,
        "company_totals": company_totals,
        "grand_total": grand_total,
        "total_items": sum(len(items) for items in grouped_items.values()),
    }


def _stock_update_redirect(selected_date):
    return redirect(f"{reverse('milk_agency:update_stock')}?date={selected_date.isoformat()}")


# -------------------------------------------------------
# STOCK DASHBOARD PAGE
# -------------------------------------------------------
@never_cache
@login_required
def stock_dashboard(request):
    return render(request, "milk_agency/stock/stock_dashboard.html")


# -------------------------------------------------------
# UPDATE STOCK PAGE
# -------------------------------------------------------
@never_cache
@login_required
def update_stock(request):
    selected_date = _parse_entry_date(request.POST.get("entry_date") if request.method == "POST" else request.GET.get("date"))

    if request.method == "POST":
        stock_updates = []

        for key, value in request.POST.items():
            if not key.startswith("stock_"):
                continue

            crates = parse_decimal(value)
            if crates <= 0:
                continue

            item_id = int(key.replace("stock_", ""))

            try:
                item = Item.objects.get(id=item_id)
            except Item.DoesNotExist:
                continue

            stock_updates.append({
                "item": item,
                "crates": crates,
            })

        updated_items = apply_stock_updates(stock_updates, entry_date=selected_date)

        if updated_items:
            messages.success(request, f"{len(updated_items)} stock entries saved for {selected_date}.")
        else:
            messages.warning(request, "No crates were entered, so nothing was saved.")

        return _stock_update_redirect(selected_date)

    return render(request, "milk_agency/stock/update_stock.html", _build_stock_context(selected_date))


@never_cache
@login_required
def edit_stock_entry_view(request, entry_id):
    entry = get_object_or_404(StockInEntry.objects.select_related("item", "company"), id=entry_id)

    if request.method == "POST":
        selected_date = _parse_entry_date(request.POST.get("entry_date"))
        crates = parse_decimal(request.POST.get("crates"))

        if crates <= 0:
            messages.error(request, "Crates must be greater than zero.")
            return _stock_update_redirect(selected_date)

        update_stock_entry(entry, crates=crates, date_value=selected_date)
        messages.success(request, "Stock entry updated successfully.")
        return _stock_update_redirect(selected_date)

    selected_date = _parse_entry_date(request.GET.get("date")) if request.GET.get("date") else entry.date
    return render(request, "milk_agency/stock/edit_stock_entry.html", {
        "entry": entry,
        "selected_date": selected_date,
    })


@never_cache
@login_required
def delete_stock_entry_view(request, entry_id):
    entry = get_object_or_404(StockInEntry.objects.select_related("item", "company"), id=entry_id)
    selected_date = entry.date

    if request.method == "POST":
        if request.POST.get("entry_date"):
            selected_date = _parse_entry_date(request.POST.get("entry_date"))

        delete_stock_entry(entry)
        messages.success(request, "Stock entry deleted successfully.")
        return _stock_update_redirect(selected_date)

    return _stock_update_redirect(selected_date)


# -------------------------------------------------------
# STOCK DATA API FOR DASHBOARD CHARTS
# -------------------------------------------------------
@never_cache
@login_required
def stock_data_api(request):
    total_items = Item.objects.count()

    total_stock_value = Item.objects.annotate(
        value=ExpressionWrapper(
            F("stock_quantity") * F("selling_price"),
            output_field=FloatField()
        )
    ).aggregate(
        total=Coalesce(Sum("value"), Value(0.0), output_field=FloatField())
    )["total"]

    all_items = Item.objects.select_related("company").values(
        "id",
        "name",
        "stock_quantity",
        "selling_price",
        company_name=F("company__name")
    )

    top_items = Item.objects.annotate(
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
        company_name=F("company__name")
    )[:10]

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

    company_data = Item.objects.values(
        company_name=F("company__name")
    ).annotate(
        total_value=Sum(
            ExpressionWrapper(
                F("stock_quantity") * F("selling_price"),
                output_field=FloatField()
            )
        )
    ).order_by("-total_value")

    return JsonResponse({
        "summary": {
            "total_items": total_items,
            "total_stock_value": float(total_stock_value or 0),
            "low_stock_count": Item.objects.filter(stock_quantity__lte=5).count(),
            "stock_in_30d": float(stock_in or 0),
            "stock_out_30d": float(stock_out or 0),
        },
        "all_items": list(all_items),
        "top_items": list(top_items),
        "company_data": list(company_data),
    })
