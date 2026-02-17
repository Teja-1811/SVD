import json
from decimal import Decimal
from django.db import transaction
from milk_agency.views_bills import generate_bill_from_order
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from customer_portal.models import CustomerOrder, CustomerOrderItem


# -------------------------------------------------------
# ADMIN ORDERS DASHBOARD
# -------------------------------------------------------
@never_cache
@login_required
def admin_orders_dashboard(request):
    pending_orders = CustomerOrder.objects.filter(status='pending').order_by('-order_date')

    return render(request, 'customer_portal/admin_orders_dashboard.html', {
        'pending_orders': pending_orders,
        'total_pending': pending_orders.count()
    })


# -------------------------------------------------------
# CONFIRM ORDER + GENERATE BILL (SAFE VERSION)
# -------------------------------------------------------
@never_cache
@login_required
def confirm_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON.'})

    quantities = data.get('quantities', [])
    order = get_object_or_404(CustomerOrder, id=order_id)

    # 🚨 Prevent double confirmation
    if order.status != 'pending':
        return JsonResponse({'success': False, 'message': 'Order already processed.'})

    try:
        with transaction.atomic():

            # -------- UPDATE ORDER ITEMS --------
            for q in quantities:
                item_id = q.get('item_id')
                quantity = int(q.get('quantity', 0))
                discount = Decimal(str(q.get('discount', 0)))

                if quantity < 0:
                    return JsonResponse({'success': False, 'message': 'Invalid quantity.'})
                if discount < 0:
                    return JsonResponse({'success': False, 'message': 'Invalid discount.'})

                if item_id is None:
                    continue

                try:
                    order_item = order.items.get(id=item_id)
                except CustomerOrderItem.DoesNotExist:
                    continue

                order_item.requested_quantity = quantity
                order_item.discount = discount
                order_item.discount_total = discount * quantity
                order_item.requested_total = (
                    order_item.requested_price * quantity
                ) - order_item.discount_total
                order_item.save()

            # -------- RECALCULATE ORDER TOTAL --------
            total_amount = sum(
                (oi.requested_total or Decimal('0.00'))
                for oi in order.items.all()
            )
            order.total_amount = total_amount
            order.save()

            # -------- GENERATE BILL FIRST --------
            bill = generate_bill_from_order(order)

            # -------- MARK ORDER CONFIRMED --------
            order.status = 'confirmed'
            order.approved_by = request.user
            order.save()

            return JsonResponse({
                'success': True,
                'message': f'Order confirmed & bill {bill.invoice_number} generated.',
                'bill_id': bill.id
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


# -------------------------------------------------------
# REJECT ORDER
# -------------------------------------------------------
@never_cache
@login_required
def reject_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})

    order = get_object_or_404(CustomerOrder, id=order_id)

    if order.status != 'pending':
        return JsonResponse({'success': False, 'message': 'Order already processed.'})

    order.status = 'rejected'
    order.approved_by = request.user
    order.save()

    return JsonResponse({'success': True, 'message': 'Order rejected successfully.'})
