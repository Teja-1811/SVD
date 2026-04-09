import json
from collections import OrderedDict
from datetime import date, timedelta

from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from milk_agency.models import Bill, BillItem, Customer, Item
from milk_agency.views_sales_summary import extract_liters_from_name


def _serialize_period(period, today):
    start_date = None
    end_date = None
    compare_start = None
    compare_end = None

    if period == "today":
        start_date = today
        end_date = today
        compare_start = today - timedelta(days=1)
        compare_end = today - timedelta(days=1)
    elif period == "week":
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        compare_start = start_date - timedelta(days=7)
        compare_end = end_date - timedelta(days=7)
    elif period == "month":
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        compare_start = (start_date - timedelta(days=1)).replace(day=1)
        compare_end = start_date - timedelta(days=1)
    elif period == "year":
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
        compare_start = start_date.replace(year=start_date.year - 1)
        compare_end = end_date.replace(year=end_date.year - 1)

    return start_date, end_date, compare_start, compare_end


@api_view(["GET"])
def api_sales_summary_by_category(request):
    period = request.GET.get("period", "overall")
    customer_id = request.GET.get("customer")
    today = timezone.now().date()
    start_date, end_date, compare_start, compare_end = _serialize_period(period, today)

    raw_categories = Item.objects.values_list("category", flat=True).distinct()
    categories = sorted({str(c).strip() for c in raw_categories if c and str(c).strip()})
    if "Others" not in categories:
        categories.append("Others")

    data_by_category = {cat: 0.0 for cat in categories}
    compare_data_by_category = {cat: 0.0 for cat in categories}
    amount_by_category = {cat: 0.0 for cat in categories}
    compare_amount_by_category = {cat: 0.0 for cat in categories}

    billitems_qs = BillItem.objects.select_related("bill", "item").filter(bill__is_deleted=False)
    compare_billitems_qs = BillItem.objects.select_related("bill", "item").filter(bill__is_deleted=False)

    if start_date and end_date:
        billitems_qs = billitems_qs.filter(bill__invoice_date__range=(start_date, end_date))
    if compare_start and compare_end:
        compare_billitems_qs = compare_billitems_qs.filter(bill__invoice_date__range=(compare_start, compare_end))

    if customer_id:
        billitems_qs = billitems_qs.filter(bill__customer_id=customer_id)
        compare_billitems_qs = compare_billitems_qs.filter(bill__customer_id=customer_id)

    for bi in billitems_qs:
        item = bi.item
        category = (item.category.strip() if item and item.category else "") or "Others"
        liters = extract_liters_from_name(item.name if item else "", fallback_unit_liters=0.0) * (bi.quantity or 0)
        data_by_category.setdefault(category, 0.0)
        amount_by_category.setdefault(category, 0.0)
        data_by_category[category] += float(liters)
        amount_by_category[category] += float(bi.total_amount or 0.0)

    for bi in compare_billitems_qs:
        item = bi.item
        category = (item.category.strip() if item and item.category else "") or "Others"
        liters = extract_liters_from_name(item.name if item else "", fallback_unit_liters=0.0) * (bi.quantity or 0)
        compare_data_by_category.setdefault(category, 0.0)
        compare_amount_by_category.setdefault(category, 0.0)
        compare_data_by_category[category] += float(liters)
        compare_amount_by_category[category] += float(bi.total_amount or 0.0)

    trend_by_category = {c: [] for c in categories}
    months = []
    cur = today.replace(day=1)
    for _ in range(12):
        months.insert(0, (cur.year, cur.month))
        cur = (cur - timedelta(days=1)).replace(day=1)

    for year, month in months:
        month_start = date(year, month, 1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        monthly_items = BillItem.objects.select_related("bill", "item").filter(
            bill__is_deleted=False,
            bill__invoice_date__range=(month_start, month_end),
        )
        if customer_id:
            monthly_items = monthly_items.filter(bill__customer_id=customer_id)

        per_cat = {c: 0.0 for c in categories}
        for bi in monthly_items:
            category = (bi.item.category.strip() if bi.item and bi.item.category else "") or "Others"
            liters = extract_liters_from_name(bi.item.name if bi.item else "", fallback_unit_liters=0.0) * (bi.quantity or 0)
            per_cat[category] = per_cat.get(category, 0.0) + float(liters)

        for category in categories:
            trend_by_category[category].append({"date": month_start.isoformat(), "volume": round(per_cat[category], 3)})

    total_volume = sum(float(v) for v in data_by_category.values())
    total_compare_volume = sum(float(v) for v in compare_data_by_category.values())
    diff_volume = total_volume - total_compare_volume
    diff_percent = (diff_volume / total_compare_volume * 100.0) if total_compare_volume else None

    year_totals = OrderedDict()
    year_qs = Bill.objects.filter(is_deleted=False)
    if customer_id:
        year_qs = year_qs.filter(customer_id=customer_id)
    years = year_qs.dates("invoice_date", "year")
    years_list = sorted({d.year for d in years}) if years else [today.year - 2, today.year - 1, today.year]

    for year in years_list:
        bi_qs = BillItem.objects.select_related("bill", "item").filter(
            bill__is_deleted=False,
            bill__invoice_date__year=year,
        )
        if customer_id:
            bi_qs = bi_qs.filter(bill__customer_id=customer_id)
        total_liters = 0.0
        for bi in bi_qs:
            total_liters += float(extract_liters_from_name(bi.item.name if bi.item else "", fallback_unit_liters=0.0) * (bi.quantity or 0))
        year_totals[str(year)] = round(total_liters, 3)

    customers = list(Customer.objects.order_by("name").values("id", "name"))
    top_categories = sorted(
        (
            {
                "category": category,
                "volume": round(float(data_by_category.get(category, 0.0)), 3),
                "amount": round(float(amount_by_category.get(category, 0.0)), 2),
            }
            for category in categories
        ),
        key=lambda row: row["volume"],
        reverse=True,
    )[:5]

    return Response(
        {
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "compare_start": compare_start,
            "compare_end": compare_end,
            "categories": categories,
            "data_by_category": data_by_category,
            "compare_data_by_category": compare_data_by_category,
            "amount_by_category": amount_by_category,
            "compare_amount_by_category": compare_amount_by_category,
            "trend_by_category": json.loads(json.dumps(trend_by_category)),
            "year_totals": year_totals,
            "total_volume": round(total_volume, 3),
            "total_compare_volume": round(total_compare_volume, 3),
            "diff_volume": round(diff_volume, 3),
            "diff_percent": round(diff_percent, 2) if diff_percent is not None else None,
            "summary": {
                "period": period,
                "categories_count": len(categories),
                "top_categories": top_categories,
            },
            "customers": customers,
            "selected_customer": int(customer_id) if customer_id else None,
        },
        status=200,
    )
