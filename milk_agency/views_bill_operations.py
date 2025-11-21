import os
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from decimal import Decimal
from .models import Bill, BillItem, Item, Customer
from .utils import process_bill_items
from django.contrib.auth.decorators import login_required

def view_bill(request, bill_id):
    bill = get_object_or_404(Bill.objects.select_related('customer'), id=bill_id)
    bill_items = BillItem.objects.filter(bill=bill).select_related('item')

    # Calculate current_due as Opening Due + Total Amount
    current_due = bill.op_due_amount + bill.total_amount

    context = {
        'bill': bill,
        'bill_items': bill_items,
        'current_due': current_due
    }
    return render(request, 'milk_agency/bills/view_bill.html', context)

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
            'current_due': float(bill.customer.due),
            'profit': float(bill.profit)
        },
        'items': [{
            'item_name': item.item.name,
            'quantity': item.quantity,
            'price_per_unit': float(item.price_per_unit),
            'discount': float(item.discount),
            'total_amount': float(item.total_amount)
        } for item in bill_items]
    }

    return JsonResponse(data)

def edit_bill(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    bill_items = BillItem.objects.filter(bill=bill)

    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        item_ids = request.POST.getlist('items')
        quantities = request.POST.getlist('quantities')
        discounts = request.POST.getlist('discounts')

        if not customer_id:
            messages.error(request, 'Customer is required.')
            return redirect('milk_agency:edit_bill', bill_id=bill_id)

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            messages.error(request, 'Customer not found.')
            return redirect('milk_agency:edit_bill', bill_id=bill_id)

        # Restore stock quantities from old bill items
        for bill_item in bill_items:
            bill_item.item.stock_quantity += bill_item.quantity
            bill_item.item.save()

        # Delete old bill items
        bill_items.delete()

        # Update bill customer if changed
        changed = bill.customer != customer
        if changed:
            old_customer = bill.customer
            old_customer.due -= bill.total_amount + bill.op_due_amount
            old_customer.save()
            bill.customer = customer
            bill.save()
            bill.op_due_amount = customer.due
        else:
            bill.op_due_amount = customer.due - bill.total_amount

        try:
            total_bill, total_profit = process_bill_items(bill, item_ids, quantities, discounts)
        except (Item.DoesNotExist, ValueError):
            messages.error(request, 'Invalid items or quantities.')
            return redirect('milk_agency:edit_bill', bill_id=bill_id)

        # Update total_amount and profit based on items
        bill.total_amount = total_bill
        bill.profit = total_profit
        bill.save()

        # Update customer due after bill update
        customer.due = bill.total_amount + bill.op_due_amount
        customer.save()

        # Monthly purchase calculation no longer available - replaced with direct calculations

        messages.success(request, 'Bill updated successfully.')
        return redirect('milk_agency:bills_dashboard')

    # GET request - display edit form
    customers = Customer.objects.all()
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

    return render(request, 'milk_agency/bills/edit_bill.html', {
        'bill': bill,
        'bill_items': bill_items,
        'customers': customers,
        'items': items
    })

@login_required
def delete_bill(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    bill_items = BillItem.objects.filter(bill=bill)

    if request.method == 'POST':
        # Restore stock quantities
        for bill_item in bill_items:
            bill_item.item.stock_quantity += bill_item.quantity
            bill_item.item.save()

        # Update customer due
        customer = bill.customer
        customer.due -= bill.total_amount + bill.op_due_amount
        customer.save()

        # Delete bill items and bill
        bill_items.delete()
        bill.delete()

        messages.success(request, f'Bill {bill.invoice_number} deleted successfully.')
        return redirect('milk_agency:bills_dashboard')

    # GET request - show confirmation page
    context = {
        'bill': bill,
        'bill_items': bill_items
    }
    return render(request, 'milk_agency/bills/delete_bill.html', context)
