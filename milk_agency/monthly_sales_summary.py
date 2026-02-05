from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum
from datetime import datetime, date, timedelta
from collections import defaultdict
from decimal import Decimal
from .models import DailySalesSummary, Customer, Bill, CustomerMonthlyCommission
import calendar
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from .monthly_sales_pdf_utils import MonthlySalesPDFGenerator
from .views_sales_summary import extract_liters_from_name


def calculate_milk_commission(volume):
    """Calculate commission for milk based on slabs."""
    volume = Decimal(str(volume))
    if volume <= 15:
        return volume * Decimal('0.2')
    elif volume <= 30:
        return Decimal('15') * Decimal('0.25') + (volume - Decimal('15')) * Decimal('0.3')
    else:
        return Decimal('15') * Decimal('0.35') + Decimal('15') * Decimal('0.35') + (volume - Decimal('30')) * Decimal('0.35')


def calculate_curd_commission(volume):
    """Calculate commission for curd based on slabs."""
    volume = Decimal(str(volume))
    if volume <= 20:
        return volume * Decimal('0.25')
    elif volume <= 35:
        return Decimal('20') * Decimal('0.25') + (volume - Decimal('20')) * Decimal('0.35')
    else:
        return Decimal('20') * Decimal('0.25') + Decimal('15') * Decimal('0.35') + (volume - Decimal('35')) * Decimal('0.5')


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

    # Calculate volumes directly from bills instead of using CustomerMonthlyPurchase
    total_volume = Decimal('0')
    milk_volume = Decimal('0')
    curd_volume = Decimal('0')

    if customer:
        # Get all bill items for the customer in the selected month
        bill_items = Bill.objects.filter(
            customer__retailer_id=customer.retailer_id,
            invoice_date__year=year,
            invoice_date__month=month,
        ).prefetch_related('items__item')

        # Calculate total volumes by item category using extract_liters_from_name
        for bill in bill_items:
            for bill_item in bill.items.all():
                category = bill_item.item.category
                quantity = bill_item.quantity
                if category and quantity:
                    category_lower = category.lower()
                    liters_per_unit = extract_liters_from_name(bill_item.item.name)
                    total_liters = Decimal(str(liters_per_unit)) * Decimal(str(quantity))
                    if category_lower == 'milk':
                        milk_volume += total_liters
                    elif category_lower == 'curd':
                        curd_volume += total_liters

        total_volume = milk_volume + curd_volume

    # Calculate average daily volumes (already in liters, no need to divide by 1000)
    avg_milk = milk_volume / days_in_month if milk_volume else Decimal('0')
    avg_curd = curd_volume / days_in_month if curd_volume else Decimal('0')
    avg_volunme = avg_milk + avg_curd

    # Calculate commissions based on slabs
    milk_commission = calculate_milk_commission(avg_milk)*days_in_month
    curd_commission = calculate_curd_commission(avg_curd)*days_in_month
    total_commission = milk_commission + curd_commission

    # Calculate effective rates for template compatibility
    milk_commission_rate = milk_commission / milk_volume if milk_volume else Decimal('0')
    curd_commission_rate = curd_commission / curd_volume if curd_volume else Decimal('0')
    commission_rate = total_commission / total_volume if total_volume else Decimal('0')

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
        'milk_volume': avg_milk,
        'curd_volume': avg_curd,
        'avg_volume' : avg_volunme,
        'milk_commission': milk_commission,
        'curd_commission': curd_commission,
        'total_commission': total_commission,
        'commission_rate': commission_rate,
        'milk_commission_rate': milk_commission_rate,
        'curd_commission_rate': curd_commission_rate,
        'remaining_due': (due_total - total_commission) if total_commission else due_total,
    }

    return render(request, 'milk_agency/dashboards_other/monthly_sales_summary.html', context)


@never_cache
@login_required
def generate_monthly_sales_pdf(request):
    """Generate PDF for monthly sales summary"""
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

    # Calculate volumes directly from bills instead of using CustomerMonthlyPurchase
    total_volume = Decimal('0')
    milk_volume = Decimal('0')
    curd_volume = Decimal('0')

    if customer:
        # Get all bill items for the customer in the selected month
        bill_items = Bill.objects.filter(
            customer__retailer_id=customer.retailer_id,
            invoice_date__year=year,
            invoice_date__month=month,
        ).prefetch_related('items__item')

        # Calculate total volumes by item category using extract_liters_from_name
        for bill in bill_items:
            for bill_item in bill.items.all():
                category = bill_item.item.category
                quantity = bill_item.quantity
                if category and quantity:
                    category_lower = category.lower()
                    liters_per_unit = extract_liters_from_name(bill_item.item.name)
                    total_liters = Decimal(str(liters_per_unit)) * Decimal(str(quantity))
                    if category_lower == 'milk':
                        milk_volume += total_liters
                    elif category_lower == 'curd':
                        curd_volume += total_liters

        total_volume = milk_volume + curd_volume

    # Use same average-based commission logic as HTML template
    days_in_month = (end_date - start_date).days + 1

    avg_milk = milk_volume / days_in_month if milk_volume else Decimal('0')
    avg_curd = curd_volume / days_in_month if curd_volume else Decimal('0')
    avg_volunme = avg_milk + avg_curd

    milk_commission = calculate_milk_commission(avg_milk) * days_in_month
    curd_commission = calculate_curd_commission(avg_curd) * days_in_month

    total_commission = milk_commission + curd_commission

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
        'milk_volume': avg_milk,
        'curd_volume': avg_curd,
        'avg_volume' : avg_volunme,
        'milk_commission': milk_commission,
        'curd_commission': curd_commission,
        'total_commission': total_commission,
        'remaining_due': (due_total - total_commission) if total_commission else due_total,
    }

    # Generate PDF
    pdf_generator = MonthlySalesPDFGenerator()
    return pdf_generator.generate_monthly_sales_pdf(context, request)


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

            # Save monthly commission if commission exists
            selected_month = request.POST.get('selected_month')
            if selected_month:
                try:
                    year, month = map(int, selected_month.split('-'))
                    # Check if commission data exists
                    commission_data = request.POST.get('commission_data')
                    if commission_data:
                        import json
                        commission_dict = json.loads(commission_data)
                        if commission_dict.get('total_commission', 0) > 0:
                            CustomerMonthlyCommission.objects.update_or_create(
                                customer=customer,
                                year=year,
                                month=month,
                                defaults={
                                    'milk_volume': commission_dict.get('milk_volume', 0),
                                    'curd_volume': commission_dict.get('curd_volume', 0),
                                    'total_volume': commission_dict.get('avg_volume', 0),
                                    'milk_commission_rate': commission_dict.get('milk_commission_rate', 0),
                                    'curd_commission_rate': commission_dict.get('curd_commission_rate', 0),
                                    'commission_amount': commission_dict.get('total_commission', 0),
                                }
                            )
                except (ValueError, json.JSONDecodeError):
                    pass  # Skip commission saving if data is invalid

            return JsonResponse({'message': f'Customer balance updated successfully to ₹{remaining_due}'})
        except (Customer.DoesNotExist, ValueError, Decimal.InvalidOperation):
            return JsonResponse({'message': 'Error updating balance. Invalid data or customer not found.'}, status=400)
    else:
        return JsonResponse({'message': 'Only POST requests allowed.'}, status=405)
