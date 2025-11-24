import json
from decimal import Decimal
from django.db import transaction
from milk_agency.views_bills import generate_bill_from_order
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from customer_portal.models import CustomerOrder, CustomerOrderItem


@never_cache
@login_required
def admin_orders_dashboard(request):
    # Get all pending orders
    pending_orders = CustomerOrder.objects.filter(status='pending').order_by('-order_date')

    context = {
        'pending_orders': pending_orders,
        'total_pending': pending_orders.count()
    }
    return render(request, 'customer_portal/admin_orders_dashboard.html', context)

@never_cache
@login_required
def confirm_order(request, order_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid JSON.'})

        quantities = data.get('quantities', [])
        order = get_object_or_404(CustomerOrder, id=order_id)

        try:
            with transaction.atomic():
                # Update quantities and discounts for each order item
                for q in quantities:
                    item_id = q.get('item_id')
                    quantity = q.get('quantity', 0)
                    discount = q.get('discount', 0)  # discount per quantity (absolute)
                    if item_id is None:
                        continue
                    try:
                        order_item = order.items.get(id=item_id)
                    except CustomerOrderItem.DoesNotExist:
                        # skip if not found
                        continue

                    # store values (use Decimal for money)
                    order_item.requested_quantity = int(quantity)
                    # discount per qty
                    order_item.discount = Decimal(str(discount)) if discount is not None else Decimal('0.00')
                    # discount total for the line
                    order_item.discount_total = order_item.discount * order_item.requested_quantity
                    # requested total after discount
                    order_item.requested_total = (order_item.requested_price * order_item.requested_quantity) - order_item.discount_total
                    order_item.save()

                # Recalculate order total
                total_amount = sum((oi.requested_total or Decimal('0.00')) for oi in order.items.all())
                order.total_amount = total_amount
                order.status = 'confirmed'
                order.approved_by = request.user
                order.save()

                # generate bill from the confirmed order
                bill = generate_bill_from_order(order)

                return JsonResponse({
                    'success': True,
                    'message': f'Order confirmed and bill {bill.invoice_number} generated successfully.',
                    'bill_id': bill.id
                })
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

@never_cache
@login_required
def reject_order(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(CustomerOrder, id=order_id)
        order.status = 'rejected'
        order.approved_by = request.user
        order.save()
        return JsonResponse({'success': True, 'message': 'Order rejected successfully.'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})
