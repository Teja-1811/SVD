import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Bill, BillItem, Customer, Item
from num2words import num2words
from decimal import Decimal
from datetime import datetime
from django.contrib.staticfiles import finders
import json
from .pdf_utils import PDFGenerator

@login_required
def bills_dashboard(request):
    # Get filter parameters
    customer_id = request.GET.get('customer', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    # Start with base queryset
    bills = Bill.objects.select_related('customer')

    # Apply filters
    if customer_id:
        try:
            bills = bills.filter(customer_id=int(customer_id))
        except ValueError:
            pass  # Invalid customer ID, ignore filter

    if start_date:
        try:
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            bills = bills.filter(invoice_date__gte=start_date_obj)
        except ValueError:
            pass  # Invalid date, ignore filter

    if end_date:
        try:
            from datetime import datetime
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            bills = bills.filter(invoice_date__lte=end_date_obj)
        except ValueError:
            pass  # Invalid date, ignore filter

    # Order by invoice date descending
    bills = bills.order_by('-invoice_date')

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(bills, 25)  # Show 25 bills per page

    try:
        bills = paginator.page(page)
    except PageNotAnInteger:
        bills = paginator.page(1)
    except EmptyPage:
        bills = paginator.page(paginator.num_pages)

    # Get all customers for the filter dropdown
    customers = Customer.objects.filter(frozen=False).order_by('name')

    context = {
        'bills': bills,
        'customers': customers,
        'selected_customer': int(customer_id) if customer_id else None,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'milk_agency/bills/bills_dashboard.html', context)

@login_required
def anonymous_bills_list(request):
    # Get bills without customers (anonymous bills)
    bills = Bill.objects.filter(customer__isnull=True).order_by('-invoice_date')

    context = {
        'bills': bills,
        'page_title': 'Anonymous Bills',
    }
    return render(request, 'milk_agency/bills/anonymous_bills_list.html', context)

@login_required
def generate_bill(request):
    # Get area filter from request
    selected_area = request.GET.get('area', '')
    
    # Get all areas for the filter dropdown
    areas = Customer.objects.exclude(area__exact='').values_list('area', flat=True).distinct().order_by('area')
    
    # Filter customers by area if provided
    if selected_area:
        customers = Customer.objects.filter(area=selected_area, frozen=False).order_by('name')
    else:
        customers = Customer.objects.filter(frozen=False).order_by('name')
    
    from django.db.models import Case, When, Value, IntegerField
    items = Item.objects.filter(frozen=False).annotate(
        category_priority=Case(
            When(category__iexact='milk', then=Value(1)),
            When(category__iexact='curd', then=Value(2)),
            When(category__iexact='buckets', then=Value(3)),
            When(category__iexact='panner', then=Value(4)),
            When(category__iexact='sweets', then=Value(5)),
            When(category__iexact='flavoured milk', then=Value(6)),
            When(category__iexact='ghee', then=Value(7)),
            default=Value(8),
            output_field=IntegerField()
        )
    ).order_by('category_priority', 'name')
    # Get distinct companies for the filter dropdown
    companies = Item.objects.exclude(company__exact='').values_list('company', flat=True).distinct().order_by('company')
    # Get distinct categories for the filter dropdown
    categories = Item.objects.exclude(category__exact='').values_list('category', flat=True).distinct().order_by('category')

    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        bill_date = request.POST.get('bill_date')
        item_ids = request.POST.getlist('items')
        quantities = request.POST.getlist('quantities')
        discounts = request.POST.getlist('discounts')

        # customer_id is now optional for anonymous bills

        # Validate and parse bill date
        if bill_date:
            try:
                from datetime import datetime
                bill_date_obj = datetime.strptime(bill_date, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Invalid date format. Please use YYYY-MM-DD format.')
                return redirect('milk_agency:generate_bill')
        else:
            bill_date_obj = timezone.now().date()

        customer = None
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                messages.error(request, 'Customer not found.')
                return redirect('milk_agency:generate_bill')

        # Generate invoice number
        today = timezone.now().date()
        last_bill_today = Bill.objects.filter(created_at__date=today).order_by('-id').first()
        invoice_number = f"INV-{today.strftime('%Y%m%d')}-{last_bill_today.id + 1 if last_bill_today else 1:04d}"

        try:
            with transaction.atomic():
                # Create a new bill
                bill = Bill.objects.create(
                    customer=customer,
                    invoice_number=invoice_number,
                    invoice_date=bill_date_obj,
                    total_amount=Decimal(0),
                    op_due_amount=customer.due if customer else Decimal(0),
                    last_paid=Decimal(0),  # Set to 0 for new bills
                    profit=Decimal(0)
                )

                total_amount = Decimal(0)
                total_profit = Decimal(0)
                updated_items = []  # Track items for stock reversion if needed

                # Create bill items
                for i, item_id in enumerate(item_ids):
                    if not item_id:
                        continue
                    quantity = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
                    discount = Decimal(discounts[i]) if i < len(discounts) and discounts[i] else Decimal(0)

                    if quantity <= 0:
                        continue

                    try:
                        item = Item.objects.get(id=item_id)
                    except Item.DoesNotExist:
                        continue

                    price_per_unit = item.selling_price
                    item_total = (price_per_unit * quantity) - (discount * quantity)
                    profit = ((price_per_unit - item.buying_price) * quantity) - (discount * quantity)

                    BillItem.objects.create(
                        bill=bill,
                        item=item,
                        price_per_unit=price_per_unit,
                        discount=discount,
                        quantity=quantity,
                        total_amount=item_total
                    )

                    # Update stock
                    item.stock_quantity -= quantity
                    item.save()
                    updated_items.append((item, quantity))  # Track for reversion

                    total_amount += item_total
                    total_profit += profit
                if total_amount == 0:
                    bill.delete()
                    messages.error(request, 'At least one item is required')
                    return redirect('milk_agency:generate_bill')

                # Update bill totals
                bill.total_amount = total_amount
                bill.profit = total_profit
                # Keep the last_paid from latest bill (set during creation), don't reset to 0
                bill.save()

                # Update customer balance only if customer exists
                if customer:
                    customer.due = bill.total_amount + bill.op_due_amount
                    customer.save()
                    # Manually trigger monthly purchase update after bill edit
                    # CustomerMonthlyPurchaseCalculator removed - monthly purchase calculation no longer available
                    messages.info(request, f'Customer updated')

            messages.success(request, f'Bill {invoice_number} generated successfully!')
            return redirect('milk_agency:view_bill', bill_id=bill.id)

        except Exception as e:
            messages.error(request, f'Error generating bill: {str(e)}')
            return redirect('milk_agency:generate_bill')

    context = {
        'customers': customers,
        'items': items,
        'areas': areas,
        'selected_area': selected_area,
        'companies': companies,
        'categories': categories,
        'current_date': timezone.now().date()
    }
    return render(request, 'milk_agency/bills/generate_bill.html', context)

def generate_bill_from_order(order):
    """
    Helper function to generate a bill from a confirmed CustomerOrder instance.
    """
    from django.db import transaction
    from decimal import Decimal
    try:
        with transaction.atomic():
            customer = order.customer
            bill_date_obj = order.order_date.date() if order.order_date else timezone.now().date()

            # Generate invoice number
            today = timezone.now().date()
            last_bill_today = Bill.objects.filter(created_at__date=today).order_by('-id').first()
            invoice_number = f"INV-{today.strftime('%Y%m%d')}-{last_bill_today.id + 1 if last_bill_today else 1:04d}"

            # Create a new bill
            bill = Bill.objects.create(
                customer=customer,
                invoice_number=invoice_number,
                invoice_date=bill_date_obj,
                total_amount=Decimal(0),
                op_due_amount=customer.due,
                last_paid=Decimal(0),  # Set to 0 for new bills
                profit=Decimal(0)
            )

            total_amount = Decimal(0)
            total_profit = Decimal(0)
            updated_items = []

            # Create bill items from order items
            for order_item in order.items.all():
                item = order_item.item
                quantity = order_item.requested_quantity
                price_per_unit = order_item.requested_price
                item_total = price_per_unit * quantity
                profit = (price_per_unit - item.buying_price) * quantity

                BillItem.objects.create(
                    bill=bill,
                    item=item,
                    price_per_unit=price_per_unit,
                    discount=Decimal(0),
                    quantity=quantity,
                    total_amount=item_total
                )

                # Update stock
                item.stock_quantity -= quantity
                item.save()
                updated_items.append((item, quantity))

                total_amount += item_total
                total_profit += profit

            if total_amount == 0:
                bill.delete()
                raise Exception('At least one item is required to generate a bill.')

            # Update bill totals
            bill.total_amount = total_amount
            bill.profit = total_profit
            # Keep the last_paid from latest bill (set during creation), don't reset to 0
            bill.save()

            # Update customer balance
            customer.due = bill.total_amount + bill.op_due_amount
            customer.save()

            # CustomerMonthlyPurchaseCalculator removed - monthly purchase calculation no longer available

            return bill
    except Exception as e:
        # Handle exceptions as needed, possibly logging or re-raising
        raise e

def generate_invoice_pdf(request, bill_id):
    """
    Generate invoice PDF and upload to GitHub, generate WhatsApp URL
    Returns a dictionary with PDF response and links
    """
    bill = get_object_or_404(Bill, id=bill_id)
    pdf_generator = PDFGenerator()
    # Regenerate PDF according to new bill model fields
    response = pdf_generator.generate_and_return_pdf(bill, request)
    return response
