from django.shortcuts import render
from django.db.models import Sum, F
from django.utils import timezone
from itertools import groupby
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from .models import Bill, Customer, Item, CashbookEntry
from .views_sales_summary import sales_summary_by_category

@login_required
@never_cache
def home(request):
    company_filter = request.GET.get('company')
    category_filter = request.GET.get('category')

    """Main dashboard view showing sales, stock, and business information."""

    # Get today's date
    today = timezone.now().date()

    # Today's sales data
    today_bills = Bill.objects.filter(invoice_date=today)
    today_sales = today_bills.aggregate(total=Sum('total_amount'))['total'] or 0
    today_bills_count = today_bills.count()

    # Total due from all customers
    total_due = Customer.objects.aggregate(total=Sum('due'))['total'] or 0

    # Cash flow data
    # Calculate total cash in from note counts instead of filtering by entry_date and entry_type
    cash_entry = CashbookEntry.objects.first()
    if cash_entry:
        today_cash_in = (cash_entry.c500 * 500) + (cash_entry.c200 * 200) + (cash_entry.c100 * 100) + (cash_entry.c50 * 50)
    else:
        today_cash_in = 0

    # Stock data calculation
    total_stock_value = Item.objects.aggregate(
        total=Sum(F('stock_quantity') * F('buying_price'))
    )['total'] or 0
    total_stock_items = Item.objects.all().count()
    # Removed duplicate calculation of total_stock_value

    # Low stock items - items where stock_quantity < pcs_count
    low_stock_items = Item.objects.filter(
        stock_quantity__lt=F('pcs_count')
    ).count()

    out_of_stock_items = Item.objects.filter(
        stock_quantity=0
    ).count()

    # Removed today's top items, active customers, and today's bills list as per request
    today_top_items = None
    today_active_customers = None
    today_bills_list = None

    # All stock items for table with calculated stock value
    all_stock_items = Item.objects.all().annotate(
        stock_value=F('stock_quantity') * F('buying_price')
    ).order_by('company', 'name')

    # Apply filters if provided
    if company_filter:
        all_stock_items = all_stock_items.filter(company__icontains=company_filter)
    if category_filter:
        all_stock_items = all_stock_items.filter(category__icontains=category_filter)

    # Group items by company
    stock_by_company = {}
    for company, items in groupby(all_stock_items, key=lambda x: x.company or 'No Company'):
        stock_by_company[company] = list(items)

    # Get distinct values for dropdowns
    companies = Item.objects.exclude(company__isnull=True).exclude(company='').values_list('company', flat=True).distinct()
    categories = Item.objects.exclude(category__isnull=True).exclude(category='').values_list('category', flat=True).distinct()

    context = {
        'companies': companies,
        'categories': categories,
        'current_date': today.strftime('%d-%m-%Y'),
        'today_sales': today_sales,
        'total_due': total_due,
        'today_bills': today_bills_count,
        'today_cash_in': today_cash_in,

        'total_stock_items': total_stock_items,
        'total_stock_value': total_stock_value,
        'low_stock_items': low_stock_items,
        'out_of_stock_items': out_of_stock_items,

        'today_top_items': today_top_items,
        'today_active_customers': today_active_customers,
        'today_bills_list': today_bills_list,

        'stock_by_company': stock_by_company,
    }

    return render(request, 'milk_agency/home/home_dashboard.html', context)



