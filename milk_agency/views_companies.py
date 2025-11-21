from django.shortcuts import render
from django.db.models import Count, Sum, F
from .models import Item

def companies_dashboard(request):
    """Display company cards with aggregated data from items."""

    # Get unique companies with aggregated data
    companies = Item.objects.filter(
        company__isnull=False
    ).exclude(
        company=''
    ).values('company').annotate(
        item_count=Count('id'),
        total_stock_value=Sum(F('stock_quantity') * F('selling_price')),
        total_stock_quantity=Sum('stock_quantity')
    ).order_by('company')

    # Convert Decimal values to float for template rendering
    for company in companies:
        company['total_stock_value'] = float(company['total_stock_value'] or 0)
        company['total_stock_quantity'] = company['total_stock_quantity'] or 0

    return render(request, 'milk_agency/dashboards_other/companies_dashboard.html', {'companies': companies})
