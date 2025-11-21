from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.db.models import Count, Sum
import json
from django.utils import timezone
from datetime import timedelta
from .models import Category, Product, Sale, SaleItem, Customer


@login_required
def home(request):
    """
    Main dashboard view with overview metrics and charts
    """
    # Dashboard metrics
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_sales = Sale.objects.count()
    total_revenue = Sale.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    low_stock_products = Product.objects.filter(stock_quantity__lt=10)

    # Today's sales data
    today = timezone.now().date()
    sales_today = Sale.objects.filter(invoice_date=today)
    today_sales_count = sales_today.count()
    today_revenue = sales_today.aggregate(total=Sum('total_amount'))['total'] or 0
    today_profit = sales_today.aggregate(total=Sum('profit'))['total'] or 0

    # Chart data for today's overview
    sales_labels = ['Today']
    sales_counts = [today_sales_count]
    revenue_data = [float(today_revenue)]
    profit_data = [float(today_profit)]

    # Top selling products
    top_products = SaleItem.objects.values('product__name').annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total_amount')
    ).order_by('-total_quantity')[:10]

    product_labels = [item['product__name'] for item in top_products]
    product_quantities = [item['total_quantity'] for item in top_products]
    product_revenues = [float(item['total_revenue'] or 0) for item in top_products]

    # Revenue by category (approximate revenue potential)
    category_revenue = Product.objects.values('category__name').annotate(
        revenue=Sum('mrp') * Sum('stock_quantity')
    ).order_by('-revenue')[:5]

    category_labels = [item['category__name'] for item in category_revenue]
    category_data = [float(item['revenue'] or 0) for item in category_revenue]

    context = {
        'total_products': total_products,
        'total_categories': total_categories,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'low_stock_products': low_stock_products,
        'sales_labels': json.dumps(sales_labels),
        'sales_counts': json.dumps(sales_counts),
        'revenue_data': json.dumps(revenue_data),
        'profit_data': json.dumps(profit_data),
        'product_labels': json.dumps(product_labels),
        'product_quantities': json.dumps(product_quantities),
        'product_revenues': json.dumps(product_revenues),
        'category_labels': json.dumps(category_labels),
        'category_data': json.dumps(category_data),
    }
    return render(request, 'general_store/home.html', context)


@login_required
def sales_trends(request):
    """
    Sales trends dashboard with filtering options
    """
    # Get filter parameters
    filter_type = request.GET.get('filter', 'month')  # today, week, month, year
    category_id = request.GET.get('category', '')  # category filter

    now = timezone.now()
    current_period_start = None
    previous_period_start = None
    previous_period_end = None
    trunc_func = None

    # Determine time period boundaries
    if filter_type == 'today':
        current_period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        previous_period_start = current_period_start - timedelta(days=1)
        previous_period_end = current_period_start - timedelta(seconds=1)
        trunc_func = TruncDay
    elif filter_type == 'week':
        current_period_start = now - timedelta(days=now.weekday())
        current_period_start = current_period_start.replace(hour=0, minute=0, second=0, microsecond=0)
        previous_period_start = current_period_start - timedelta(days=7)
        previous_period_end = current_period_start - timedelta(seconds=1)
        trunc_func = TruncWeek
    elif filter_type == 'year':
        current_period_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_period_start = current_period_start.replace(year=current_period_start.year - 1)
        previous_period_end = current_period_start - timedelta(seconds=1)
        trunc_func = TruncYear
    else:  # month (default)
        current_period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_period_start = (current_period_start - timedelta(days=1)).replace(day=1)
        previous_period_end = current_period_start - timedelta(seconds=1)
        trunc_func = TruncMonth

    # Base querysets for current period
    current_sales_base = Sale.objects.filter(invoice_date__gte=current_period_start)
    if category_id:
        current_sales_base = current_sales_base.filter(items__product__category_id=category_id).distinct()

    # Current period metrics
    current_total_sales = current_sales_base.count()
    current_total_revenue = current_sales_base.aggregate(total=Sum('total_amount'))['total'] or 0
    current_total_profit = current_sales_base.aggregate(total=Sum('profit'))['total'] or 0

    # Previous period metrics
    previous_sales_base = Sale.objects.filter(
        invoice_date__gte=previous_period_start,
        invoice_date__lte=previous_period_end
    )
    if category_id:
        previous_sales_base = previous_sales_base.filter(items__product__category_id=category_id).distinct()

    previous_total_sales = previous_sales_base.count()
    previous_total_revenue = previous_sales_base.aggregate(total=Sum('total_amount'))['total'] or 0
    previous_total_profit = previous_sales_base.aggregate(total=Sum('profit'))['total'] or 0

    # Calculate percentage changes
    sales_change = ((current_total_sales - previous_total_sales) / previous_total_sales * 100) if previous_total_sales > 0 else 0
    revenue_change = ((current_total_revenue - previous_total_revenue) / previous_total_revenue * 100) if previous_total_revenue > 0 else 0
    profit_change = ((current_total_profit - previous_total_profit) / previous_total_profit * 100) if previous_total_profit > 0 else 0

    # Chart data for current period
    sales_by_period = current_sales_base.annotate(
        period=trunc_func('invoice_date')
    ).values('period').annotate(
        count=Count('id'),
        revenue=Sum('total_amount'),
        profit=Sum('profit')
    ).order_by('period')

    labels = []
    sales_counts = []
    revenue_data = []
    profit_data = []

    for item in sales_by_period:
        if filter_type == 'today':
            labels.append(item['period'].strftime('%H:%M'))
        elif filter_type == 'week':
            labels.append(item['period'].strftime('%a'))
        elif filter_type == 'year':
            labels.append(item['period'].strftime('%b'))
        else:  # month
            labels.append(item['period'].strftime('%d'))

        sales_counts.append(item['count'])
        revenue_data.append(float(item['revenue'] or 0))
        profit_data.append(float(item['profit'] or 0))

    # Top products for current period
    top_products_base = SaleItem.objects.filter(
        sale__invoice_date__gte=current_period_start
    )
    if category_id:
        top_products_base = top_products_base.filter(product__category_id=category_id)

    top_products = top_products_base.values('product__name').annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total_amount')
    ).order_by('-total_quantity')[:10]

    product_labels = [item['product__name'] for item in top_products]
    product_quantities = [item['total_quantity'] for item in top_products]
    product_revenues = [float(item['total_revenue'] or 0) for item in top_products]

    # Category-wise analytics for current period
    category_analytics_base = SaleItem.objects.filter(
        sale__invoice_date__gte=current_period_start
    )
    if category_id:
        category_analytics_base = category_analytics_base.filter(product__category_id=category_id)

    category_analytics = category_analytics_base.values('product__category__name').annotate(
        total_sales=Count('sale', distinct=True),
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total_amount'),
        total_profit=Sum('sale__profit')
    ).order_by('-total_revenue')

    # Add average sale value to each category
    category_analytics = list(category_analytics)
    for item in category_analytics:
        item['avg_sale_value'] = item['total_revenue'] / item['total_sales'] if item['total_sales'] else 0

    # Get top and bottom performing categories
    top_category = category_analytics[0] if category_analytics else None
    bottom_category = category_analytics[-1] if category_analytics else None

    # Category summary
    category_summary = {
        'total_categories': len(category_analytics),
        'top_category': top_category['product__category__name'] if top_category else 'N/A',
        'top_category_revenue': float(top_category['total_revenue'] or 0) if top_category else 0,
        'bottom_category': bottom_category['product__category__name'] if bottom_category else 'N/A',
        'bottom_category_revenue': float(bottom_category['total_revenue'] or 0) if bottom_category else 0,
    }

    # Get all categories for filter dropdown
    categories = Category.objects.all()

    context = {
        'filter_type': filter_type,
        'category_id': category_id,
        'categories': categories,
        'current_total_sales': current_total_sales,
        'current_total_revenue': current_total_revenue,
        'current_total_profit': current_total_profit,
        'previous_total_sales': previous_total_sales,
        'previous_total_revenue': previous_total_revenue,
        'previous_total_profit': previous_total_profit,
        'sales_change': sales_change,
        'revenue_change': revenue_change,
        'profit_change': profit_change,
        'labels': json.dumps(labels),
        'sales_counts': json.dumps(sales_counts),
        'revenue_data': json.dumps(revenue_data),
        'profit_data': json.dumps(profit_data),
        'product_labels': json.dumps(product_labels),
        'product_quantities': json.dumps(product_quantities),
        'product_revenues': json.dumps(product_revenues),
        'category_summary': category_summary,
        'category_analytics': list(category_analytics),
    }
    return render(request, 'general_store/sales_trends.html', context)
