import os
from decimal import Decimal

from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Bill, BillItem, Item, Customer
from .order_pricing import DELIVERY_ITEM_CODE
from .utils import process_bill_items
from customer_portal.models import CustomerOrder


def _find_linked_customer_order(bill):
    if not bill.customer_id:
        return None

    # `order_date` is already a DateField, so this must stay an exact date match.
    order = (
        CustomerOrder.objects.filter(
            customer_id=bill.customer_id,
            order_date=bill.invoice_date,
        )
        .filter(
            total_amount=bill.total_amount,
        )
        .order_by("-id")
        .first()
    )
    if order:
        return order

    order = (
        CustomerOrder.objects.filter(
            customer_id=bill.customer_id,
            order_date=bill.invoice_date,
            approved_total_amount=bill.total_amount,
        )
        .order_by("-id")
        .first()
    )
    if order:
        return order

    candidates = CustomerOrder.objects.filter(
        customer_id=bill.customer_id,
        order_date=bill.invoice_date,
    ).order_by("-id")
    for candidate in candidates:
        if Decimal(candidate.approved_total_amount or 0) + Decimal(candidate.delivery_charge or 0) == Decimal(bill.total_amount or 0):
            return candidate
    return candidates.first()


# =========================================================
# VIEW BILL
# =========================================================
@login_required
def view_bill(request, bill_id):
    bill = get_object_or_404(Bill.objects.select_related('customer').filter(is_deleted=False), id=bill_id)
    bill_items = BillItem.objects.filter(bill=bill).select_related('item')
    linked_order = _find_linked_customer_order(bill)
    delivery_charge_item = bill_items.filter(item__code=DELIVERY_ITEM_CODE).first()
    delivery_charge = Decimal(delivery_charge_item.total_amount if delivery_charge_item else 0)
    if delivery_charge == 0 and linked_order:
        delivery_charge = Decimal(linked_order.delivery_charge or 0)
    display_items = bill_items.exclude(item__code=DELIVERY_ITEM_CODE)

    current_due = bill.op_due_amount + bill.total_amount

    return render(request, 'milk_agency/bills/view_bill.html', {
        'bill': bill,
        'bill_items': display_items,
        'current_due': current_due,
        'linked_order': linked_order,
        'delivery_charge': delivery_charge,
        'items_subtotal': Decimal(bill.total_amount or 0) - delivery_charge,
    })


# =========================================================
# AJAX BILL DETAILS
# =========================================================
@login_required
def get_bill_details_ajax(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id, is_deleted=False)
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
    bill = get_object_or_404(Bill, id=bill_id, is_deleted=False)
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
    bill = get_object_or_404(Bill, id=bill_id, is_deleted=False)
    bill_items = BillItem.objects.filter(bill=bill)

    if request.method == 'POST':
        customer = bill.customer

        with transaction.atomic():
            # -------- RESTORE STOCK --------
            for bi in bill_items.select_related('item'):
                bi.item.stock_quantity += bi.quantity
                bi.item.save(update_fields=['stock_quantity'])

            # -------- HANDLE LINKED ORDER --------
            order = _find_linked_customer_order(bill)

            if order:
                order.status = "cancelled"
                order.approved_total_amount = 0
                order.save(update_fields=['status', 'approved_total_amount'])

            bill_items.delete()
            bill.is_deleted = True
            bill.save(update_fields=['is_deleted'])

            # -------- RECALCULATE CUSTOMER DUE --------
            if customer:
                customer.due = customer.get_actual_due()
                customer.save(update_fields=['due'])

        messages.success(request, "Bill deleted. Stock restored & due recalculated.")
        return redirect('milk_agency:bills_dashboard')

    return render(request, 'milk_agency/bills/delete_bill.html', {
        'bill': bill,
        'bill_items': bill_items
    })
