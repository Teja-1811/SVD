import os
import json
from decimal import Decimal, ROUND_UP
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Bill, BillItem, Customer, Item, Company, CustomerMonthlyCommission
from .pdf_utils import PDFGenerator


# =========================================================
# BILLS DASHBOARD
# =========================================================
@login_required
def bills_dashboard(request):
    customer_id = request.GET.get('customer', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    bills = Bill.objects.select_related('customer')

    if customer_id:
        try:
            bills = bills.filter(customer_id=int(customer_id))
        except ValueError:
            pass

    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            bills = bills.filter(invoice_date__gte=start_date_obj)
        except ValueError:
            pass

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            bills = bills.filter(invoice_date__lte=end_date_obj)
        except ValueError:
            pass

    bills = bills.order_by('-invoice_date')

    paginator = Paginator(bills, 25)
    page = request.GET.get('page', 1)

    try:
        bills = paginator.page(page)
    except PageNotAnInteger:
        bills = paginator.page(1)
    except EmptyPage:
        bills = paginator.page(paginator.num_pages)

    customers = Customer.objects.filter(frozen=False).order_by('name')

    return render(request, 'milk_agency/bills/bills_dashboard.html', {
        'bills': bills,
        'customers': customers,
        'selected_customer': int(customer_id) if customer_id else None,
        'start_date': start_date,
        'end_date': end_date,
    })


# =========================================================
# GENERATE BILL (FINAL SAFE VERSION)
# =========================================================
@login_required
def generate_bill(request):
    selected_area = request.GET.get('area', '')

    areas = Customer.objects.exclude(area__exact='').values_list('area', flat=True).distinct().order_by('area')

    if selected_area:
        customers = Customer.objects.filter(area=selected_area, frozen=False).order_by('name')
    else:
        customers = Customer.objects.filter(frozen=False).order_by('name')

    items = Item.objects.filter(frozen=False).order_by('category', 'name')
    companies = Company.objects.filter(items__isnull=False).distinct().order_by('name')
    categories = Item.objects.exclude(category__exact='').values_list('category', flat=True).distinct().order_by('category')

    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        bill_date = request.POST.get('bill_date')
        item_ids = request.POST.getlist('items')
        quantities = request.POST.getlist('quantities')
        discounts = request.POST.getlist('discounts')

        try:
            bill_date_obj = datetime.strptime(bill_date, '%Y-%m-%d').date() if bill_date else timezone.now().date()
        except ValueError:
            messages.error(request, 'Invalid date format.')
            return redirect('milk_agency:generate_bill')

        customer = None
        commission_to_deduct = None

        if customer_id:
            customer = get_object_or_404(Customer, id=customer_id)
            commission_to_deduct = CustomerMonthlyCommission.objects.filter(
                customer=customer, status=False
            ).first()

        # ---------- SAFE UNIQUE INVOICE ----------
        now = timezone.now()
        prefix = now.strftime('%Y%m%d%H%M%S')
        last_bill = Bill.objects.filter(invoice_number__startswith=f"INV-{prefix}").order_by('-invoice_number').first()
        counter = int(last_bill.invoice_number.split('-')[-1]) + 1 if last_bill else 1
        invoice_number = f"INV-{prefix}-{counter:04d}"

        updated_items = []

        try:
            with transaction.atomic():

                bill = Bill.objects.create(
                    customer=customer,
                    invoice_number=invoice_number,
                    invoice_date=bill_date_obj,
                    total_amount=Decimal("0"),
                    op_due_amount=customer.due if customer else Decimal("0"),
                    last_paid=Decimal("0"),
                    profit=Decimal("0")
                )

                total_amount = Decimal("0")
                total_profit = Decimal("0")

                for i, item_id in enumerate(item_ids):
                    if not item_id:
                        continue

                    qty = int(quantities[i]) if quantities[i] else 0
                    if qty <= 0:
                        continue

                    item = get_object_or_404(Item, id=item_id)
                    discount = Decimal(discounts[i]) if discounts[i] else Decimal("0")

                    price = Decimal(str(item.selling_price))
                    item_total = (price * qty) - (discount * qty)
                    profit = ((price - Decimal(str(item.buying_price))) * qty) - (discount * qty)

                    BillItem.objects.create(
                        bill=bill,
                        item=item,
                        price_per_unit=price,
                        discount=discount,
                        quantity=qty,
                        total_amount=item_total
                    )

                    item.stock_quantity -= qty
                    item.save()
                    updated_items.append((item, qty))

                    total_amount += item_total
                    total_profit += profit

                if total_amount <= 0:
                    raise Exception("No valid items in bill.")

                rounded_total = total_amount.quantize(Decimal('1'), rounding=ROUND_UP)

                if commission_to_deduct and rounded_total > 0:
                    commission_amt = commission_to_deduct.commission_amount
                    adjusted_total = rounded_total - commission_amt
                    if adjusted_total < 0:
                        adjusted_total = Decimal("0")

                    bill.total_amount = adjusted_total
                    bill.commission_deducted = commission_amt
                    bill.commission_month = commission_to_deduct.month
                    bill.commission_year = commission_to_deduct.year

                    commission_to_deduct.status = True
                    commission_to_deduct.save()
                else:
                    bill.total_amount = rounded_total

                bill.profit = total_profit
                bill.save()

                if customer:
                    customer.due = customer.get_actual_due()
                    customer.save()

            messages.success(request, f'Bill {invoice_number} generated successfully!')
            return redirect('milk_agency:view_bill', bill_id=bill.id)

        except Exception as e:
            for item, qty in updated_items:
                item.stock_quantity += qty
                item.save()

            messages.error(request, f'Error generating bill: {str(e)}')
            return redirect('milk_agency:generate_bill')

    return render(request, 'milk_agency/bills/generate_bill.html', {
        'customers': customers,
        'items': items,
        'areas': areas,
        'selected_area': selected_area,
        'companies': companies,
        'categories': categories,
        'current_date': timezone.now().date()
    })


# =========================================================
# GENERATE BILL FROM ORDER
# =========================================================
def generate_bill_from_order(order):
    with transaction.atomic():
        customer = order.customer
        bill_date_obj = order.order_date.date() if order.order_date else timezone.now().date()

        now = timezone.now()
        prefix = now.strftime('%Y%m%d%H%M%S')
        invoice_number = f"INV-{prefix}"

        bill = Bill.objects.create(
            customer=customer,
            invoice_number=invoice_number,
            invoice_date=bill_date_obj,
            total_amount=Decimal("0"),
            op_due_amount=customer.due,
            last_paid=Decimal("0"),
            profit=Decimal("0")
        )

        total_amount = Decimal("0")
        total_profit = Decimal("0")

        for oi in order.items.all():
            item = oi.item
            qty = oi.requested_quantity
            price = oi.requested_price
            discount_total = getattr(oi, 'discount_total', Decimal("0"))

            item_total = (price * qty) - discount_total
            profit = ((price - item.buying_price) * qty) - discount_total

            BillItem.objects.create(
                bill=bill,
                item=item,
                price_per_unit=price,
                discount=oi.discount,
                quantity=qty,
                total_amount=item_total
            )

            item.stock_quantity -= qty
            item.save()

            total_amount += item_total
            total_profit += profit

        if total_amount <= 0:
            raise Exception("Invalid order amount")

        bill.total_amount = total_amount
        bill.profit = total_profit
        bill.save()

        customer.due = customer.get_actual_due()
        customer.save()

        return bill


# =========================================================
# PDF GENERATION
# =========================================================
def generate_invoice_pdf(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    pdf_generator = PDFGenerator()
    return pdf_generator.generate_and_return_pdf(bill, request)
