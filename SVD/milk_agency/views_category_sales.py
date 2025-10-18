from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Sum, Count, F, Q, Case, When, Value
import re
from django.db.models.functions import TruncDate, TruncMonth, TruncYear
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Item, Bill, BillItem, CustomerMonthlyPurchase

# Categories where quantity represents volume in liters (based on item model categories)
liquid_categories = ['Milk', 'Curd']

def get_volume_per_unit(code):
    """Get volume in liters per unit based on item code - extract number and convert ml to liters"""
    if not code:
        return 0.0
    digits = ''.join(filter(str.isdigit, code))
    if digits:
        return int(digits) / 1000  # ml to liters
    return 0.0

def category_sales_dashboard(request):
    """Main category sales dashboard view"""
    return render(request, 'milk_agency/dashboards_other/category_sales_dashboard.html')

def get_today_category_sales(request):
    """Get today's category-wise sales data"""
    today = timezone.now().date()

    # Get today's bill items with category information
    today_sales = BillItem.objects.filter(
        bill__invoice_date=today
    ).select_related('item', 'bill')

    category_data = {}
    for sale in today_sales:
        category = sale.item.category if sale.item.category else 'Uncategorized'
        if category in liquid_categories:
            volume_per_unit = get_volume_per_unit(sale.item.code)
            volume = sale.quantity * volume_per_unit
        else:
            volume = 0

        if category not in category_data:
            category_data[category] = {
                'volume': 0,
                'amount': 0,
                'count': 0
            }

        category_data[category]['volume'] += float(volume)
        category_data[category]['amount'] += float(sale.total_amount)
        category_data[category]['count'] += 1

    return JsonResponse({
        'date': today.strftime('%Y-%m-%d'),
        'categories': category_data,
        'total_volume': sum(cat['volume'] for cat in category_data.values()),
        'total_amount': sum(cat['amount'] for cat in category_data.values())
    })

def get_week_category_sales(request):
    """Get current week's category-wise sales data"""
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())

    week_sales = BillItem.objects.filter(
        bill__invoice_date__gte=week_start,
        bill__invoice_date__lte=today
    ).select_related('item', 'bill')

    category_data = {}
    for sale in week_sales:
        category = sale.item.category if sale.item.category else 'Uncategorized'
        if category in liquid_categories:
            volume_per_unit = get_volume_per_unit(sale.item.code)
            volume = sale.quantity * volume_per_unit
        else:
            volume = 0

        if category not in category_data:
            category_data[category] = {
                'volume': 0,
                'amount': 0,
                'count': 0
            }

        category_data[category]['volume'] += float(volume)
        category_data[category]['amount'] += float(sale.total_amount)
        category_data[category]['count'] += 1

    return JsonResponse({
        'week_start': week_start.strftime('%Y-%m-%d'),
        'week_end': today.strftime('%Y-%m-%d'),
        'categories': category_data,
        'total_volume': sum(cat['volume'] for cat in category_data.values()),
        'total_amount': sum(cat['amount'] for cat in category_data.values())
    })

def get_month_category_sales(request):
    """Get current month's category-wise sales data"""
    today = timezone.now().date()
    month_start = today.replace(day=1)

    month_sales = BillItem.objects.filter(
        bill__invoice_date__gte=month_start,
        bill__invoice_date__lte=today
    ).select_related('item', 'bill')

    category_data = {}
    for sale in month_sales:
        category = sale.item.category if sale.item.category else 'Uncategorized'
        if category in liquid_categories:
            volume_per_unit = get_volume_per_unit(sale.item.code)
            volume = sale.quantity * volume_per_unit
        else:
            volume = 0

        if category not in category_data:
            category_data[category] = {
                'volume': 0,
                'amount': 0,
                'count': 0
            }

        category_data[category]['volume'] += float(volume)
        category_data[category]['amount'] += float(sale.total_amount)
        category_data[category]['count'] += 1

    return JsonResponse({
        'month': today.strftime('%Y-%m'),
        'categories': category_data,
        'total_volume': sum(cat['volume'] for cat in category_data.values()),
        'total_amount': sum(cat['amount'] for cat in category_data.values())
    })

def get_year_category_sales(request):
    """Get current year's category-wise sales data"""
    today = timezone.now().date()
    year_start = today.replace(month=1, day=1)

    year_sales = BillItem.objects.filter(
        bill__invoice_date__gte=year_start,
        bill__invoice_date__lte=today
    ).select_related('item', 'bill')

    category_data = {}
    for sale in year_sales:
        category = sale.item.category if sale.item.category else 'Uncategorized'
        if category in liquid_categories:
            volume_per_unit = get_volume_per_unit(sale.item.code)
            volume = sale.quantity * volume_per_unit
        else:
            volume = 0

        if category not in category_data:
            category_data[category] = {
                'volume': 0,
                'amount': 0,
                'count': 0
            }

        category_data[category]['volume'] += float(volume)
        category_data[category]['amount'] += float(sale.total_amount)
        category_data[category]['count'] += 1

    return JsonResponse({
        'year': today.year,
        'categories': category_data,
        'total_volume': sum(cat['volume'] for cat in category_data.values()),
        'total_amount': sum(cat['amount'] for cat in category_data.values())
    })

def get_monthly_category_history(request):
    """Get monthly historical data for line graphs"""
    # Get last 12 months of data
    today = timezone.now().date()
    twelve_months_ago = today - timedelta(days=365)

    # Get all relevant bill items for the period
    monthly_sales = BillItem.objects.filter(
        bill__invoice_date__gte=twelve_months_ago,
        item__category__in=liquid_categories
    ).select_related('item', 'bill').order_by('bill__invoice_date')

    # Aggregate data in Python
    from collections import defaultdict
    monthly_totals = defaultdict(lambda: {'total_volume': 0.0, 'total_amount': 0.0})
    category_monthly_data = defaultdict(lambda: defaultdict(lambda: {'volume': 0.0, 'amount': 0.0}))

    for sale in monthly_sales:
        month = sale.bill.invoice_date.replace(day=1)
        month_str = month.strftime('%b %Y')
        category = sale.item.category if sale.item.category else 'Uncategorized'

        volume_per_unit = get_volume_per_unit(sale.item.code)
        volume = sale.quantity * volume_per_unit

        monthly_totals[month_str]['total_volume'] += float(volume)
        monthly_totals[month_str]['total_amount'] += float(sale.total_amount)

        category_monthly_data[month_str][category]['volume'] += float(volume)
        category_monthly_data[month_str][category]['amount'] += float(sale.total_amount)

    # Format data for charts
    labels = sorted(monthly_totals.keys())
    total_volume_data = [monthly_totals[month]['total_volume'] for month in labels]
    total_amount_data = [monthly_totals[month]['total_amount'] for month in labels]

    # Get unique categories
    all_categories = set()
    for month_data in category_monthly_data.values():
        all_categories.update(month_data.keys())

    # Prepare datasets for Chart.js
    datasets = []
    colors = ['rgb(75, 192, 192)', 'rgb(255, 99, 132)', 'rgb(54, 162, 235)',
              'rgb(255, 205, 86)', 'rgb(153, 102, 255)', 'rgb(255, 159, 64)']

    for i, category in enumerate(sorted(all_categories)):
        category_data = []
        for month in labels:
            volume = category_monthly_data.get(month, {}).get(category, {}).get('volume', 0)
            category_data.append(volume)

        datasets.append({
            'label': category,
            'data': category_data,
            'borderColor': colors[i % len(colors)],
            'backgroundColor': colors[i % len(colors)].replace('rgb', 'rgba').replace(')', ', 0.2)'),
            'tension': 0.4
        })

    return JsonResponse({
        'labels': labels,
        'datasets': datasets,
        'total_volume_data': total_volume_data,
        'total_amount_data': total_amount_data
    })

def get_yearly_category_history(request):
    """Get yearly historical data for line graphs"""
    # Get last 5 years of data
    today = timezone.now().date()
    five_years_ago = today.replace(year=today.year - 5)

    # Get all relevant bill items for the period
    yearly_sales = BillItem.objects.filter(
        bill__invoice_date__gte=five_years_ago,
        item__category__in=liquid_categories
    ).select_related('item', 'bill').order_by('bill__invoice_date')

    # Aggregate data in Python
    from collections import defaultdict
    yearly_totals = defaultdict(lambda: {'total_volume': 0.0, 'total_amount': 0.0})
    category_yearly_data = defaultdict(lambda: defaultdict(lambda: {'volume': 0.0, 'amount': 0.0}))

    for sale in yearly_sales:
        year = sale.bill.invoice_date.year
        year_str = str(year)
        category = sale.item.category if sale.item.category else 'Uncategorized'

        volume_per_unit = get_volume_per_unit(sale.item.code)
        volume = sale.quantity * volume_per_unit

        yearly_totals[year_str]['total_volume'] += float(volume)
        yearly_totals[year_str]['total_amount'] += float(sale.total_amount)

        category_yearly_data[year_str][category]['volume'] += float(volume)
        category_yearly_data[year_str][category]['amount'] += float(sale.total_amount)

    # Format data for charts
    labels = sorted(yearly_totals.keys())
    total_volume_data = [yearly_totals[year]['total_volume'] for year in labels]
    total_amount_data = [yearly_totals[year]['total_amount'] for year in labels]

    # Get unique categories
    all_categories = set()
    for year_data in category_yearly_data.values():
        all_categories.update(year_data.keys())

    # Prepare datasets for Chart.js
    datasets = []
    colors = ['rgb(75, 192, 192)', 'rgb(255, 99, 132)', 'rgb(54, 162, 235)',
              'rgb(255, 205, 86)', 'rgb(153, 102, 255)', 'rgb(255, 159, 64)']

    for i, category in enumerate(sorted(all_categories)):
        category_data = []
        for year in labels:
            volume = category_yearly_data.get(year, {}).get(category, {}).get('volume', 0)
            category_data.append(volume)

        datasets.append({
            'label': category,
            'data': category_data,
            'borderColor': colors[i % len(colors)],
            'backgroundColor': colors[i % len(colors)].replace('rgb', 'rgba').replace(')', ', 0.2)'),
            'tension': 0.4
        })

    return JsonResponse({
        'labels': labels,
        'datasets': datasets,
        'total_volume_data': total_volume_data,
        'total_amount_data': total_amount_data
    })

def get_category_sales_summary(request):
    """Get summary statistics for the dashboard"""
    today = timezone.now().date()

    def calculate_summary(start_date, end_date):
        sales = BillItem.objects.filter(
            bill__invoice_date__gte=start_date,
            bill__invoice_date__lte=end_date,
            item__category__in=liquid_categories
        ).select_related('item', 'bill')

        total_volume = 0.0
        total_amount = 0.0

        for sale in sales:
            volume_per_unit = get_volume_per_unit(sale.item.code)
            volume = sale.quantity * volume_per_unit
            total_volume += float(volume)
            total_amount += float(sale.total_amount)

        return total_volume, total_amount

    # Today's summary
    today_volume, today_amount = calculate_summary(today, today)

    # This week's summary
    week_start = today - timedelta(days=today.weekday())
    week_volume, week_amount = calculate_summary(week_start, today)

    # This month's summary
    month_start = today.replace(day=1)
    month_volume, month_amount = calculate_summary(month_start, today)

    # This year's summary
    year_start = today.replace(month=1, day=1)
    year_volume, year_amount = calculate_summary(year_start, today)

    return JsonResponse({
        'today': {
            'volume': today_volume,
            'amount': today_amount
        },
        'week': {
            'volume': week_volume,
            'amount': week_amount
        },
        'month': {
            'volume': month_volume,
            'amount': month_amount
        },
        'year': {
            'volume': year_volume,
            'amount': year_amount
        }
    })
