import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .models import Bill, BillItem, Customer, Item
from io import BytesIO
from num2words import num2words
from decimal import Decimal
from datetime import datetime
from django.contrib.staticfiles import finders
import json
from .pdf_utils import PDFGenerator

@login_required
def bills_dashboard(request):
    bills = Bill.objects.select_related('customer').order_by('-invoice_date')

    context = {
        'bills': bills
    }
    return render(request, 'milk_agency/bills/bills_dashboard.html', context)

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
    
    items = Item.objects.all().order_by('name')
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

        if not customer_id:
            messages.error(request, 'Customer is required.')
            return redirect('milk_agency:generate_bill')

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
                messages.info(request, f'Starting bill creation for customer {customer.name}')
                # Create a new bill
                bill = Bill.objects.create(
                    customer=customer,
                    invoice_number=invoice_number,
                    invoice_date=bill_date_obj,
                    total_amount=Decimal(0),
                    op_due_amount=customer.due,
                    profit=Decimal(0)
                )
                messages.info(request, f'Bill created with ID {bill.id}')

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
                    profit = (price_per_unit - item.buying_price) * quantity

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

                messages.info(request, f'Total amount calculated: {total_amount}')
                if total_amount == 0:
                    bill.delete()
                    messages.error(request, 'At least one item is required')
                    return redirect('milk_agency:generate_bill')

                # Update bill totals
                bill.total_amount = total_amount
                bill.profit = total_profit
                bill.last_paid = customer.last_paid_balance
                bill.save()
                messages.info(request, f'Bill updated and saved')

                # Update customer balance to totalbill + op_due
                customer.due = bill.total_amount + bill.op_due_amount
                customer.last_paid_balance = Decimal(0)  # Reset last paid balance after applying to bill
                customer.save()
                # Manually trigger monthly purchase update after bill edit
                from .customer_monthly_purchase_calculator import CustomerMonthlyPurchaseCalculator
                bill_date = bill.invoice_date
                year = bill_date.year
                month = bill_date.month
                CustomerMonthlyPurchaseCalculator.calculate_customer_monthly_purchase(customer, year, month)
                messages.info(request, f'Customer updated')
                # Generate PDF after saving bill
                messages.info(request, 'Starting PDF generation')
                try:
                    pdf_generator = PDFGenerator()
                    pdf_path = pdf_generator.generate_invoice_pdf(bill)
                    if os.path.exists(pdf_path):
                        messages.info(request, 'PDF generated and file saved successfully')
                    else:
                        raise Exception('PDF file not saved')
                except Exception as pdf_error:
                    # PDF generation failed, delete bill and revert changes

                    # Revert stock changes
                    for item, qty in updated_items:
                        item.stock_quantity += qty
                        item.save()
                    # Revert customer due
                    customer.due = customer.due - bill.total_amount - bill.op_due_amount
                    customer.last_paid_balance = bill.last_paid
                    customer.save()
                    bill.delete()
                    messages.error(request, f'PDF generation failed: {str(pdf_error)}. Bill not saved.')
                    return redirect('milk_agency:generate_bill')

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
            bill.last_paid = customer.last_paid_balance
            bill.save()

            # Update customer balance
            customer.due = bill.total_amount + bill.op_due_amount
            customer.last_paid_balance = Decimal(0)
            customer.save()

            # Trigger monthly purchase update
            from .customer_monthly_purchase_calculator import CustomerMonthlyPurchaseCalculator
            bill_date = bill.invoice_date
            year = bill_date.year
            month = bill_date.month
            CustomerMonthlyPurchaseCalculator.calculate_customer_monthly_purchase(customer, year, month)

            # Generate PDF
            pdf_generator = PDFGenerator()
            pdf_path = pdf_generator.generate_invoice_pdf(bill)
            if not os.path.exists(pdf_path):
                raise Exception('PDF file not saved')

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
