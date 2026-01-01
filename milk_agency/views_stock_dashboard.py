from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.db.models import Sum, F, FloatField, ExpressionWrapper, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from .models import Item, BillItem, Company
from datetime import datetime, timedelta


# -------------------------------------------------------
# STOCK DASHBOARD PAGE
# -------------------------------------------------------
@never_cache
@login_required
def stock_dashboard(request):
    return render(request, 'milk_agency/stock/stock_dashboard.html')


# -------------------------------------------------------
# UPDATE STOCK PAGE
# -------------------------------------------------------
@never_cache
@login_required
def update_stock(request):

    if request.method == 'POST':
        updated_items = []

        for key, value in request.POST.items():
            if key.startswith('stock_') and value:
                item_id = int(key.replace('stock_', ''))
                crates = float(value)

                try:
                    item = Item.objects.get(id=item_id)
                    old_quantity = item.stock_quantity

                    # crates * pieces per crate
                    pcs = item.pcs_count if item.pcs_count > 0 else 1
                    added_qty = crates * pcs

                    item.stock_quantity += added_qty
                    item.save()

                    updated_items.append({
                        'name': item.name,
                        'old_quantity': old_quantity,
                        'new_quantity': item.stock_quantity,
                        'added_quantity': added_qty,
                        'difference': added_qty
                    })

                except Item.DoesNotExist:
                    continue

        return redirect('milk_agency:update_stock')

    # GET request
    from itertools import groupby
    from collections import OrderedDict

    # Items grouped by category
    items = Item.objects.filter(frozen=False).select_related('company').order_by('category', 'name')

    grouped_items = {}
    for category, group in groupby(items, key=lambda x: (x.category or 'others').lower()):
        grouped_items[category] = sorted(list(group), key=lambda x: x.name.lower())

    # Category display order
    category_order = ['milk', 'curd', 'cups', 'buckets', 'panner', 'sweets', 'flavoured milk', 'ghee', 'others']

    from collections import OrderedDict
    ordered_grouped = OrderedDict()
    for cat in category_order:
        ordered_grouped[cat] = grouped_items.get(cat, [])

    total_items = sum(len(items) for items in ordered_grouped.values())

    # Company filter — FIXED to use ForeignKey
    companies = list(
        Company.objects.filter(items__frozen=False)
        .distinct()
        .values_list('name', flat=True)
    )

    return render(request, 'milk_agency/stock/update_stock.html', {
        'grouped_items': ordered_grouped,
        'total_items': total_items,
        'companies': companies
    })


# -------------------------------------------------------
# STOCK DATA API FOR DASHBOARD CHARTS
# -------------------------------------------------------
@never_cache
@login_required
def stock_data_api(request):

    # SUMMARY
    total_items = Item.objects.count()

    total_stock_value = Item.objects.annotate(
        value=ExpressionWrapper(
            F('stock_quantity') * F('selling_price'),
            output_field=FloatField()
        )
    ).aggregate(
        total=Coalesce(Sum('value'), Value(0.0), output_field=FloatField())
    )['total']

    all_items = Item.objects.select_related('company').values(
            'id',
            'name',
            'stock_quantity',
            'selling_price',
            company_name=F('company__name')
        )

    top_items = Item.objects.annotate(
        stock_value=ExpressionWrapper(
            F('stock_quantity') * F('selling_price'),
            output_field=FloatField()
        )
    ).order_by('-stock_value').values(
        'id',
        'name',
        'stock_quantity',
        'selling_price',
        'stock_value',
        company_name=F('company__name')
    )[:10]


    # Stock-out last 30 days
    thirty_days_ago = datetime.today() - timedelta(days=30)

    stock_out = BillItem.objects.filter(
        bill__invoice_date__gte=thirty_days_ago
    ).aggregate(
        total=Coalesce(Sum('quantity'), Value(0.0), output_field=FloatField())
    )['total']

    # COMPANY-WISE STOCK VALUE — FIXED
    company_data = Item.objects.values(
        company_name=F('company__name')
    ).annotate(
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
            'low_stock_count': Item.objects.filter(stock_quantity__lte=5).count(),
            'stock_in_30d': 0,  # removed model
            'stock_out_30d': stock_out,
        },
        'all_items': list(all_items),
        'top_items': list(top_items),
        'company_data': list(company_data),
    })
