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
        import json
        from .views_bills import generate_bill_from_order

        data = json.loads(request.body)
        quantities = data.get('quantities', [])

        order = get_object_or_404(CustomerOrder, id=order_id)

        # Update quantities of order items
        for q in quantities:
            item_id = q.get('item_id')
            quantity = q.get('quantity')
            if item_id is not None and quantity is not None:
                try:
                    order_item = order.items.get(id=item_id)
                    order_item.requested_quantity = quantity
                    order_item.requested_total = quantity * order_item.requested_price
                    order_item.save()
                except CustomerOrderItem.DoesNotExist:
                    continue

        # Recalculate total amount
        total_amount = sum(item.requested_total for item in order.items.all())
        order.total_amount = total_amount

        order.status = 'confirmed'
        order.approved_by = request.user
        order.save()

        # Generate bill from the confirmed order
        try:
            bill = generate_bill_from_order(order)
            return JsonResponse({
                'success': True,
                'message': f'Order confirmed and bill {bill.invoice_number} generated successfully.',
                'bill_id': bill.id
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Order confirmed but bill generation failed: {str(e)}'
            })

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
