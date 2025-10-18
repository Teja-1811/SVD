from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum
from datetime import datetime, date, timedelta
from collections import defaultdict
from decimal import Decimal
from .models import DailySalesSummary, Customer, Bill, CustomerMonthlyPurchase
import calendar
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import JsonResponse


@never_cache
@login_required
def monthly_sales_summary(request):
    selected_month = request.GET.get('date', datetime.now().strftime('%Y-%m'))
    selected_area = request.GET.get('area', '')
    selected_customer = request.GET.get('customer', '')

    try:
        year, month = map(int, selected_month.split('-'))
    except (ValueError, AttributeError):
        year = datetime.now().year
        month = datetime.now().month

    # All unique areas from customers
    areas = (
        Customer.objects.exclude(area__exact='')
        .values_list('area', flat=True)
        .distinct()
        .order_by('area')
    )

    # Customers filtered by area
    if selected_area:
        customers = Customer.objects.filter(area=selected_area).order_by('name')
    else:
        customers = Customer.objects.all().order_by('name')

    # Filter sales by customer if selected
    if selected_customer:
        try:
            customer = Customer.objects.get(id=selected_customer)
            sales_data = DailySalesSummary.objects.filter(
                date__year=year, date__month=month, retailer_id=customer.retailer_id
            )
        except Customer.DoesNotExist:
            sales_data = DailySalesSummary.objects.none()
            customer = None
    else:
        sales_data = DailySalesSummary.objects.filter(
            date__year=year, date__month=month
        )
        customer = None

    # Paid & due amounts - calculate from actual bills
    paid_amount = 0
    due_amount = 0
    total_sales = 0
    due_total = 0
    if customer:
        bills = Bill.objects.filter(
            customer__retailer_id=customer.retailer_id,
            invoice_date__year=year,
            invoice_date__month=month,
        ).order_by('invoice_date')

        # Use aggregates for consistent totals
        invoice_total = bills.aggregate(total=Sum('total_amount'))['total'] or 0
        paid_total = bills.aggregate(total=Sum('last_paid'))['total'] or 0

        # Opening due: from first bill in the month or customer.due if no bills
        opening_due = bills.first().op_due_amount if bills.exists() else customer.due

        # Due = opening due + monthly invoices - monthly payments
        due_total = opening_due + invoice_total - paid_total

        # assign to variables used in template
        paid_amount = paid_total
        due_amount = due_total
        # total sales should be invoice total (what was billed in this month)
        total_sales = invoice_total

    # Total items
    total_items = 0
    for sale in sales_data:
        try:
            items = sale.get_item_list()
            total_items += sum(item['quantity'] for item in items)
        except Exception:
            continue

    # --- your existing bills & items aggregation logic ---
    customer_bills_dict = {}
    customer_items_data = defaultdict(dict)
    unique_items = set()
    unique_codes = set()

    if customer:
        bills = Bill.objects.filter(
            customer__retailer_id=customer.retailer_id,
            invoice_date__year=year,
            invoice_date__month=month,
        ).order_by('invoice_date')

        aggregated_bills = defaultdict(
            lambda: {
                'total_amount': 0,
                'last_paid': 0,
                'op_due_amount': None,   # store separately so we don’t double-count
                'items': defaultdict(int),
            }
        )

        for bill in bills:
            date_key = bill.invoice_date.strftime('%Y-%m-%d')

            # Aggregate invoice totals & payments
            aggregated_bills[date_key]['total_amount'] += bill.total_amount
            aggregated_bills[date_key]['last_paid'] += bill.last_paid

            # Only take op_due_amount from the first bill of the day
            if aggregated_bills[date_key]['op_due_amount'] is None:
                aggregated_bills[date_key]['op_due_amount'] = bill.op_due_amount

            # Aggregate item quantities
            for bill_item in bill.items.all():
                item_name = bill_item.item.name
                item_code = bill_item.item.code
                unique_items.add(item_name)
                unique_codes.add(item_code)
                aggregated_bills[date_key]['items'][item_code] += bill_item.quantity

        # Build per-date customer bills dictionary
        for date_key, data in aggregated_bills.items():
            op_due = data['op_due_amount'] or 0
            customer_bills_dict[date_key] = {
                'invoice_date': datetime.strptime(date_key, '%Y-%m-%d').date(),
                'total_amount': data['total_amount'],
                'paid_amount': data['last_paid'],
                'due_amount': data['total_amount'] - data['last_paid'] + op_due,
            }

            for item_code, quantity in data['items'].items():
                customer_items_data[item_code][date_key] = quantity

    # Convert sets to sorted lists for template use
    unique_items = sorted(list(unique_items))
    unique_codes = sorted(list(unique_codes))


    total_quantity_per_item = {
        item_code: sum(customer_items_data[item_code].values())
        for item_code in unique_codes
    }

    days_in_month = calendar.monthrange(year, month)[1]
    date_range = [date(year, month, day) for day in range(1, days_in_month + 1)]

    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)

    monthly_purchase_data = None
    if customer:
        try:
            monthly_purchase_data = CustomerMonthlyPurchase.objects.get(
                customer=customer, year=year, month=month
            )
        except CustomerMonthlyPurchase.DoesNotExist:
            monthly_purchase_data = None

    # Calculate commission based on total volume and rate
    total_commission = Decimal('0')
    avg_milk = Decimal('0')
    avg_curd = Decimal('0')
    avg_volunme = Decimal('0')
    rate = Decimal('0')
    total_volume = Decimal('0')
    if monthly_purchase_data:
        total_volume = monthly_purchase_data.total_purchase_volume
        milk_volume = monthly_purchase_data.milk_volume or Decimal('0')
        curd_volume = monthly_purchase_data.curd_volume or Decimal('0')
        avg_milk = milk_volume / days_in_month if days_in_month else Decimal('0')
        avg_curd = curd_volume / days_in_month if days_in_month else Decimal('0')
        avg_volunme = total_volume / days_in_month if days_in_month else Decimal('0')
        rate = customer.get_commission_rate(avg_volunme) if customer else Decimal('0')
        total_commission = total_volume * rate

    context = {
        'areas': areas,
        'selected_area': selected_area,
        'customers': customers,
        'selected_customer': selected_customer,
        'selected_customer_obj': customer,
        'selected_date': start_date,
        'start_date': start_date,
        'end_date': end_date,
        'sales_data': sales_data,
        'total_sales': total_sales,
        'paid_amount': paid_amount,
        'due_amount': due_amount,
        'total_items': total_items,
        'customer_bills': customer_bills_dict,
        'customer_items_data': customer_items_data,
        'unique_items': unique_items,
        'unique_codes': unique_codes,
        'date_range': date_range,
        'total_quantity_per_item': total_quantity_per_item,
        'monthly_purchase_data': monthly_purchase_data,
        'milk_volume': avg_milk,
        'curd_volume': avg_curd,
        'avg_volume' : avg_volunme,
        'commission_rate' : rate,
        'total_commission': total_commission,
        'remaining_due': (due_total - total_commission) if total_commission else due_total,
    }

    return render(request, 'milk_agency/dashboards_other/monthly_sales_summary.html', context)


@never_cache
@login_required
def update_remaining_due(request):
    if request.method == 'POST':
        customer_id = request.POST.get('customer_id')
        remaining_due_str = request.POST.get('remaining_due')
        try:
            customer = Customer.objects.get(id=customer_id)
            remaining_due = Decimal(remaining_due_str)
            customer.due = remaining_due
            customer.save()
            return JsonResponse({'message': f'Customer balance updated successfully to ₹{remaining_due}'})
        except (Customer.DoesNotExist, ValueError, Decimal.InvalidOperation):
            return JsonResponse({'message': 'Error updating balance. Invalid data or customer not found.'}, status=400)
    else:
        return JsonResponse({'message': 'Only POST requests allowed.'}, status=405)
