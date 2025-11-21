from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.db.models import Sum, F, FloatField, ExpressionWrapper, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from .models import Item, BillItem
from datetime import datetime, timedelta

@never_cache
@login_required
def stock_dashboard(request):
    """
    Main view for the stock dashboard page.
    """
    return render(request, 'milk_agency/stock/stock_dashboard.html')

@never_cache
@login_required
def update_stock(request):
    """
    View for updating stock quantities for items.
    """
    if request.method == 'POST':
        updated_items = []

        # Process each item from the form
        for key, value in request.POST.items():
            if key.startswith('stock_') and value:
                item_id = int(key.replace('stock_', ''))
                crates = int(value)

                try:
                    item = Item.objects.get(id=item_id)
                    old_quantity = item.stock_quantity
                    # Calculate total units: crates * pcs_count
                    additional_quantity = crates * (item.pcs_count if item.pcs_count > 0 else 1)
                    item.stock_quantity += additional_quantity
                    item.save()

                    updated_items.append({
                        'name': item.name,
                        'old_quantity': old_quantity,
                        'new_quantity': item.stock_quantity,
                        'added_quantity': additional_quantity,
                        'difference': additional_quantity
                    })

                except Item.DoesNotExist:
                    continue

        #if updated_items:
            # messages.success(request, f'Successfully updated stock for {len(updated_items)} items.')

        return redirect('milk_agency:update_stock')

    # GET request - display the form
    from itertools import groupby
    from collections import OrderedDict

    items = Item.objects.filter(frozen=False).order_by('category', 'name')

    # Group items by category
    grouped_items = {}
    for category, group in groupby(items, key=lambda x: (x.category or 'others').lower()):
        grouped_items[category] = sorted(list(group), key=lambda x: x.name.lower())

    # Define custom order for categories
    category_order = ['milk', 'curd', 'buckets', 'panner', 'sweets', 'flavoured milk', 'ghee', 'others']
    ordered_grouped = OrderedDict()
    for cat in category_order:
        ordered_grouped[cat] = grouped_items.get(cat, [])

    # Check if there are any items at all
    total_items = sum(len(items) for items in ordered_grouped.values())

    # Get distinct companies for filtering
    companies = list(Item.objects.filter(frozen=False).exclude(company__isnull=True).exclude(company='').values_list('company', flat=True).distinct())
    companies = list(dict.fromkeys(companies))

    return render(request, 'milk_agency/stock/update_stock.html', {'grouped_items': ordered_grouped, 'total_items': total_items, 'companies': companies})

@never_cache
@login_required
def stock_data_api(request):
    """
    REST-like endpoint that returns JSON data for the stock dashboard.
    """
    # Overall stock summary
    total_items = Item.objects.count()
    total_stock_value = Item.objects.annotate(
        value=ExpressionWrapper(
            F('stock_quantity') * F('selling_price'),
            output_field=FloatField()
        )
    ).aggregate(total=Coalesce(Sum('value'), Value(0.0), output_field=FloatField()))['total']

    # All items with current stock and value
    all_items = Item.objects.values(
        'id', 'name', 'company', 'stock_quantity', 'selling_price'
    )

    # Top 10 items by stock value
    top_items = Item.objects.annotate(
        stock_value=ExpressionWrapper(
            F('stock_quantity') * F('selling_price'),
            output_field=FloatField()
        )
    ).order_by('-stock_value')[:10].values(
        'id', 'name', 'company', 'stock_quantity', 'selling_price', 'stock_value'
    )

    # Stock movement last 30 days
    thirty_days_ago = datetime.today() - timedelta(days=30)
    # Removed stock_in calculation as StockEntry model is removed
    stock_in = 0

    stock_out = BillItem.objects.filter(
        bill__invoice_date__gte=thirty_days_ago
    ).aggregate(total=Coalesce(Sum('quantity'), Value(0.0), output_field=FloatField()))['total']

    # Category-wise stock value (grouped by company)
    category_data = Item.objects.values('company').annotate(
        total_value=Sum(
            ExpressionWrapper(
                F('stock_quantity') * F('selling_price'),
                output_field=FloatField()
            )
        )
    ).order_by('-total_value')

    return JsonResponse({
        'summary': {
            'total_items': total_items,
            'total_stock_value': float(total_stock_value),
            'low_stock_count': all_items.filter(stock_quantity__lte=5).count(),
            'stock_in_30d': stock_in,
            'stock_out_30d': stock_out,
        },
        'all_items': list(all_items),
        'top_items': list(top_items),
        'category_data': list(category_data),
    })
