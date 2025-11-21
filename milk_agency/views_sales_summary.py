import re
import json
from collections import defaultdict, OrderedDict
from datetime import timedelta, date
from django.shortcuts import render
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from .models import Bill, BillItem, Item, Customer

# Helper: derive liters per single unit from Item.name
def extract_liters_from_name(item_name, fallback_unit_liters=None):
    """
    Tries to parse strings like:
      - "FCM500" -> 500 -> treated as ml -> 0.5 L
      - "Curd450g" -> 450 g -> treated as 0.45 L (assume g ~ ml for dairy)
      - "UHT1L" -> 1 L
      - "Paneer200g" -> 0.2 L (approx, may be non-liquid but we treat g/ml -> /1000)
      - "Bottle 2L" -> 2 L

    Rules (conservative):
      - If unit explicitly 'l' or 'L' => liters = number
      - If unit 'ml' or 'g' => liters = number / 1000
      - If unit 'kg' => treat as liters = number (approx 1kg ~ 1L for dairy)
      - If no unit but a number exists:
          * if number < 10 -> treat as liters (e.g., "1" -> 1L)
          * else -> treat as ml and divide by 1000 (e.g., 500 -> 0.5L)
      - If parse fails -> fallback_unit_liters (if provided) else 0.0
    """
    if not item_name:
        return float(fallback_unit_liters or 0.0)

    s = item_name.strip()
    # Find number and optional unit
    m = re.search(r'(?i)(\d+(?:\.\d+)?)(?:\s?)(ml|l|kg|g)?', s)
    if not m:
        return float(fallback_unit_liters or 0.0)

    num = float(m.group(1))
    unit = (m.group(2) or '').lower()

    if unit == 'l':
        return float(num)
    if unit in ('ml', 'g'):
        return float(num) / 1000.0
    if unit == 'kg':
        # approximate: 1 kg = 1 L for dairy / milk-like items
        return float(num)

    # no unit found, apply heuristic
    if num < 10:
        # often means liters: "1L" may be written "1"
        return float(num)
    # likely milliliters / grams
    return float(num) / 1000.0


@login_required
@never_cache
def sales_summary_by_category(request):
    # --- Parse filters ---
    period = request.GET.get('period', 'overall')  # overall, today, week, month, year
    customer_id = request.GET.get('customer', '')  # optional customer filter (id)

    today = timezone.now().date()
    start_date = None
    end_date = None
    compare_start = None
    compare_end = None

    # compute ranges similar to your existing logic
    if period == 'today':
        start_date = today
        end_date = today
        compare_start = today - timedelta(days=1)
        compare_end = today - timedelta(days=1)
    elif period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        compare_start = start_date - timedelta(days=7)
        compare_end = end_date - timedelta(days=7)
    elif period == 'month':
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        compare_start = (start_date - timedelta(days=1)).replace(day=1)
        compare_end = start_date - timedelta(days=1)
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
        compare_start = start_date.replace(year=start_date.year - 1)
        compare_end = end_date.replace(year=end_date.year - 1)
    else:
        # overall: no date filters
        start_date = None
        end_date = None

    # --- Filters for Bills / BillItems ---
    bill_filter = {}
    compare_bill_filter = {}

    if customer_id:
        bill_filter['customer_id'] = customer_id
        compare_bill_filter['customer_id'] = customer_id

    # BillItem base query for main period
    billitems_qs = BillItem.objects.select_related('bill', 'item').all()
    if start_date and end_date:
        billitems_qs = billitems_qs.filter(bill__invoice_date__range=(start_date, end_date), **({'bill__customer_id': customer_id} if customer_id else {}))
    elif customer_id:
        billitems_qs = billitems_qs.filter(bill__customer_id=customer_id)

    # BillItem for compare period
    compare_billitems_qs = BillItem.objects.select_related('bill', 'item').all()
    if compare_start and compare_end:
        compare_billitems_qs = compare_billitems_qs.filter(bill__invoice_date__range=(compare_start, compare_end), **({'bill__customer_id': customer_id} if customer_id else {}))
    elif customer_id:
        compare_billitems_qs = compare_billitems_qs.filter(bill__customer_id=customer_id)

    # --- Determine categories dynamically from Item table ---
    # Use category field; items with empty/null category -> "Others"
    raw_categories = Item.objects.values_list('category', flat=True).distinct()
    categories = []
    for c in raw_categories:
        if c and str(c).strip():
            categories.append(str(c).strip())
    categories = sorted(set(categories))  # alphabetical
    if 'Others' not in categories:
        categories.append('Others')  # ensure Others bucket

    # Initialize sums
    data_by_category = {cat: 0.0 for cat in categories}
    compare_data_by_category = {cat: 0.0 for cat in categories}

    # total amounts per category (money) to display optionally
    amount_by_category = {cat: 0.0 for cat in categories}
    compare_amount_by_category = {cat: 0.0 for cat in categories}

    # --- Aggregate main period volumes & amounts ---
    for bi in billitems_qs:
        item = bi.item
        cat = (item.category.strip() if item and item.category else '') or 'Others'
        if cat not in data_by_category:
            # if new category appears at runtime (should be rare), add it
            data_by_category.setdefault(cat, 0.0)
            amount_by_category.setdefault(cat, 0.0)

        # liters per single unit
        liters_per_unit = extract_liters_from_name(item.name if item else '', fallback_unit_liters=0.0)
        total_liters = liters_per_unit * (bi.quantity or 0)

        data_by_category[cat] = data_by_category.get(cat, 0.0) + float(total_liters)
        amount_by_category[cat] = amount_by_category.get(cat, 0.0) + float(bi.total_amount or 0.0)

    # --- Aggregate compare period volumes & amounts ---
    for bi in compare_billitems_qs:
        item = bi.item
        cat = (item.category.strip() if item and item.category else '') or 'Others'
        if cat not in compare_data_by_category:
            compare_data_by_category.setdefault(cat, 0.0)
            compare_amount_by_category.setdefault(cat, 0.0)

        liters_per_unit = extract_liters_from_name(item.name if item else '', fallback_unit_liters=0.0)
        total_liters = liters_per_unit * (bi.quantity or 0)

        compare_data_by_category[cat] = compare_data_by_category.get(cat, 0.0) + float(total_liters)
        compare_amount_by_category[cat] = compare_amount_by_category.get(cat, 0.0) + float(bi.total_amount or 0.0)

    # Ensure all categories keys exist
    for c in categories:
        data_by_category.setdefault(c, 0.0)
        compare_data_by_category.setdefault(c, 0.0)
        amount_by_category.setdefault(c, 0.0)
        compare_amount_by_category.setdefault(c, 0.0)

    # --- Trend data by category over the chosen period ---
    trend_by_category = {c: [] for c in categories}

    if period == 'today':
        # daily trend for last 2 days (yesterday & today)
        dates = []
        d0 = today - timedelta(days=1)
        dates = [d0, today]
        for d in dates:
            per_cat = {c: 0.0 for c in categories}
            items_on_day = BillItem.objects.select_related('item','bill').filter(bill__invoice_date=d)
            if customer_id:
                items_on_day = items_on_day.filter(bill__customer_id=customer_id)
            for bi in items_on_day:
                cat = (bi.item.category.strip() if bi.item and bi.item.category else '') or 'Others'
                liters = extract_liters_from_name(bi.item.name) * (bi.quantity or 0)
                per_cat[cat] = per_cat.get(cat, 0.0) + float(liters)
            for c in categories:
                trend_by_category[c].append({'date': d.isoformat(), 'volume': round(per_cat[c], 3)})
    elif period == 'week':
        # weekly buckets for last 4 weeks
        weeks = []
        cur = today - timedelta(days=today.weekday())  # current week start (Monday)
        for i in range(4):
            ws = cur - timedelta(days=7 * i)
            we = ws + timedelta(days=6)
            weeks.append((ws, we))
        for (ws, we) in weeks:
            per_cat = {c: 0.0 for c in categories}
            items_in_week = BillItem.objects.select_related('item','bill').filter(bill__invoice_date__range=(ws, we))
            if customer_id:
                items_in_week = items_in_week.filter(bill__customer_id=customer_id)
            for bi in items_in_week:
                cat = (bi.item.category.strip() if bi.item and bi.item.category else '') or 'Others'
                liters = extract_liters_from_name(bi.item.name) * (bi.quantity or 0)
                per_cat[cat] = per_cat.get(cat, 0.0) + float(liters)
            label = ws.isoformat()
            for c in categories:
                trend_by_category[c].append({'date': label, 'volume': round(per_cat[c], 3)})
    elif period == 'month':
        # monthly for last 12 months
        months = []
        cur = today.replace(day=1)
        for i in range(12):
            months.insert(0, (cur.year, cur.month))
            cur = (cur - timedelta(days=1)).replace(day=1)
        for (y, m) in months:
            month_start = date(y, m, 1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            per_cat = {c: 0.0 for c in categories}
            items_in_month = BillItem.objects.select_related('item','bill').filter(bill__invoice_date__range=(month_start, month_end))
            if customer_id:
                items_in_month = items_in_month.filter(bill__customer_id=customer_id)
            for bi in items_in_month:
                cat = (bi.item.category.strip() if bi.item and bi.item.category else '') or 'Others'
                liters = extract_liters_from_name(bi.item.name) * (bi.quantity or 0)
                per_cat[cat] = per_cat.get(cat, 0.0) + float(liters)
            label = month_start.isoformat()
            for c in categories:
                trend_by_category[c].append({'date': label, 'volume': round(per_cat[c], 3)})
    else:
        # for 'year', 'custom', 'overall' - monthly between start_date and end_date, or last 12 months
        if start_date and end_date:
            months = []
            cur = start_date.replace(day=1)
            while cur <= end_date:
                months.append((cur.year, cur.month))
                next_month = (cur + timedelta(days=32)).replace(day=1)
                cur = next_month
        else:
            months = []
            cur = today.replace(day=1)
            for i in range(12):
                months.insert(0, (cur.year, cur.month))
                cur = (cur - timedelta(days=1)).replace(day=1)
        for (y, m) in months:
            month_start = date(y, m, 1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            per_cat = {c: 0.0 for c in categories}
            items_in_month = BillItem.objects.select_related('item','bill').filter(bill__invoice_date__range=(month_start, month_end))
            if customer_id:
                items_in_month = items_in_month.filter(bill__customer_id=customer_id)
            for bi in items_in_month:
                cat = (bi.item.category.strip() if bi.item and bi.item.category else '') or 'Others'
                liters = extract_liters_from_name(bi.item.name) * (bi.quantity or 0)
                per_cat[cat] = per_cat.get(cat, 0.0) + float(liters)
            label = month_start.isoformat()
            for c in categories:
                trend_by_category[c].append({'date': label, 'volume': round(per_cat[c], 3)})

    # --- Comparison metrics (yesterday vs today, etc.) ---
    def sum_period(category_data):
        # sum over all keys of given dict
        return sum(category_data.values())

    # Overall totals
    total_volume = sum(float(v) for v in data_by_category.values())
    total_compare_volume = sum(float(v) for v in compare_data_by_category.values())

    # differences for display: absolute and percent
    diff_volume = total_volume - total_compare_volume
    diff_percent = (diff_volume / total_compare_volume * 100.0) if total_compare_volume else None

    # --- Year-wise bar: sum of all categories per year (milk+curd+others) ---
    # We'll consider all BillItems (respecting customer filter) and group by bill year
    year_totals = OrderedDict()
    year_qs = Bill.objects.all()
    if customer_id:
        year_qs = year_qs.filter(customer_id=customer_id)
    years = year_qs.dates('invoice_date', 'year')
    # If .dates returns empty, fallback to last 3 years
    if not years:
        current_year = today.year
        years_list = [current_year - 2, current_year - 1, current_year]
    else:
        years_list = sorted({d.year for d in years})

    for y in years_list:
        # items in that year
        bi_qs = BillItem.objects.select_related('bill', 'item').filter(bill__invoice_date__year=y)
        if customer_id:
            bi_qs = bi_qs.filter(bill__customer_id=customer_id)
        total_l = 0.0
        for bi in bi_qs:
            total_l += float(extract_liters_from_name(bi.item.name) * (bi.quantity or 0))
        year_totals[str(y)] = round(total_l, 3)

    # --- Prepare serializable JSON structures for JS/Chart.js ---
    context = {
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'compare_start': compare_start,
        'compare_end': compare_end,
        'categories': categories,
        'data_by_category': data_by_category,
        'compare_data_by_category': compare_data_by_category,
        'amount_by_category': amount_by_category,
        'compare_amount_by_category': compare_amount_by_category,
        'trend_by_category_json': json.dumps(trend_by_category, default=str),
        'data_by_category_json': json.dumps(data_by_category),
        'compare_data_by_category_json': json.dumps(compare_data_by_category),
        'year_totals_json': json.dumps(year_totals),
        'total_volume': round(total_volume, 3),
        'total_compare_volume': round(total_compare_volume, 3),
        'diff_volume': round(diff_volume, 3),
        'diff_percent': round(diff_percent, 2) if diff_percent is not None else None,
        'customers': Customer.objects.order_by('name').all(),
        'selected_customer': int(customer_id) if customer_id else None
    }

    return render(request, 'milk_agency/dashboards_other/sales_summary_by_category.html', context)
