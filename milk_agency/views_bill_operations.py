import os
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Bill, BillItem, Item, Customer
from .utils import process_bill_items
from customer_portal.models import CustomerOrder


# =========================================================
# VIEW BILL
# =========================================================
@login_required
def view_bill(request, bill_id):
    bill = get_object_or_404(Bill.objects.select_related('customer'), id=bill_id)
    bill_items = BillItem.objects.filter(bill=bill).select_related('item')

    current_due = bill.op_due_amount + bill.total_amount

    return render(request, 'milk_agency/bills/view_bill.html', {
        'bill': bill,
        'bill_items': bill_items,
        'current_due': current_due
    })


# =========================================================
# AJAX BILL DETAILS
# =========================================================
@login_required
def get_bill_details_ajax(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    bill_items = BillItem.objects.filter(bill=bill).select_related('item')

    data = {
        'bill': {
            'id': bill.id,
            'invoice_number': bill.invoice_number,
            'customer_name': bill.customer.name,
            'invoice_date': bill.invoice_date.strftime('%Y-%m-%d'),
            'total_amount': float(bill.total_amount),
            'op_due_amount': float(bill.op_due_amount),
            'last_paid': float(bill.last_paid),
            'current_due': float(bill.customer.get_actual_due()),
            'profit': float(bill.profit)
        },
        'items': [{
            'item_name': bi.item.name,
            'quantity': bi.quantity,
            'price_per_unit': float(bi.price_per_unit),
            'discount': float(bi.discount),
            'total_amount': float(bi.total_amount)
        } for bi in bill_items]
    }

    return JsonResponse(data)


# =========================================================
# EDIT BILL (SAFE VERSION)
# =========================================================
@login_required
def edit_bill(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    bill_items = BillItem.objects.filter(bill=bill)

    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        item_ids = request.POST.getlist('items')
        quantities = request.POST.getlist('quantities')
        discounts = request.POST.getlist('discounts')
        invoice_date = request.POST.get('invoice_date')

        if not customer_id:
            messages.error(request, 'Customer is required.')
            return redirect('milk_agency:edit_bill', bill_id=bill_id)

        customer = get_object_or_404(Customer, id=customer_id)

        # Update invoice date
        if invoice_date:
            try:
                from datetime import datetime
                bill.invoice_date = datetime.strptime(invoice_date, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Invalid invoice date format.')
                return redirect('milk_agency:edit_bill', bill_id=bill_id)

        # -------- RESTORE STOCK --------
        for bi in bill_items:
            bi.item.stock_quantity += bi.quantity
            bi.item.save()

        # Remove old items
        bill_items.delete()

        # -------- UPDATE BILL CUSTOMER --------
        bill.customer = customer
        bill.op_due_amount = customer.get_actual_due()

        try:
            total_bill, total_profit = process_bill_items(bill, item_ids, quantities, discounts)
        except Exception:
            messages.error(request, 'Invalid items or quantities.')
            return redirect('milk_agency:edit_bill', bill_id=bill_id)

        bill.total_amount = total_bill
        bill.profit = total_profit
        bill.save()

        # -------- RECALCULATE DUE SAFELY --------
        customer.due = customer.get_actual_due()
        customer.save()

        messages.success(request, 'Bill updated successfully.')
        return redirect('milk_agency:bills_dashboard')

    customers = Customer.objects.all()
    items = Item.objects.filter(frozen=False).order_by('category', 'name')

    return render(request, 'milk_agency/bills/edit_bill.html', {
        'bill': bill,
        'bill_items': bill_items,
        'customers': customers,
        'items': items
    })


# =========================================================
# DELETE BILL (SAFE VERSION)
# =========================================================
@login_required
def delete_bill(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    bill_items = BillItem.objects.filter(bill=bill)

    if request.method == 'POST':
        customer = bill.customer

        # -------- RESTORE STOCK --------
        for bi in bill_items:
            bi.item.stock_quantity += bi.quantity
            bi.item.save()

        # -------- HANDLE LINKED ORDER --------
        order = CustomerOrder.objects.filter(
            customer=customer,
            order_date__date=bill.invoice_date,
            total_amount=bill.total_amount
        ).order_by('-id').first()

        if order:
            order.status = "cancelled"
            order.approved_total_amount = 0
            order.save()

        bill_items.delete()
        bill.delete()

        # -------- RECALCULATE CUSTOMER DUE --------
        if customer:
            customer.due = customer.get_actual_due()
            customer.save()

        messages.success(request, "Bill deleted. Stock restored & due recalculated.")
        return redirect('milk_agency:bills_dashboard')

    return render(request, 'milk_agency/bills/delete_bill.html', {
        'bill': bill,
        'bill_items': bill_items
    })
