import json
from decimal import Decimal

from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.db import transaction
from django.shortcuts import get_object_or_404

from customer_portal.models import CustomerOrder, CustomerOrderItem
from milk_agency.views_bills import generate_bill_from_order


# ======================================================
# 1️⃣ ADMIN ORDERS DASHBOARD (PENDING ORDERS)
# ======================================================
@api_view(['GET'])
def api_admin_orders_dashboard(request):
    """
    Returns all pending customer orders
    """

    pending_orders = CustomerOrder.objects.filter(
        status="pending"
    ).order_by("-order_date")

    orders = []

    for order in pending_orders:
        orders.append({
            "order_id": order.id,
            "order_date": str(order.order_date),
            "customer_id": order.customer.id if order.customer else None,
            "customer_name": order.customer.name if order.customer else "",
            "total_amount": float(order.total_amount or 0),
            "items_count": order.items.count()
        })

    return Response({
        "total_pending": pending_orders.count(),
        "orders": orders
    })


# ======================================================
# 2️⃣ ORDER DETAILS (ITEMS WITH PRICE & QTY)
# ======================================================
@api_view(['GET'])
def api_order_detail(request, order_id):
    """
    Get full order details including items
    """

    order = get_object_or_404(CustomerOrder, id=order_id)

    items = []
    for oi in order.items.all():
        items.append({
            "order_item_id": oi.id,
            "item_id": oi.item.id,
            "item_name": oi.item.name,
            "price": float(oi.requested_price),
            "requested_quantity": oi.requested_quantity,
            "discount_per_qty": float(oi.discount or 0),
            "discount_total": float(oi.discount_total or 0),
            "requested_total": float(oi.requested_total or 0)
        })

    return Response({
        "order_id": order.id,
        "order_date": str(order.order_date),
        "customer_name": order.customer.name if order.customer else "",
        "status": order.status,
        "total_amount": float(order.total_amount or 0),
        "items": items
    })


# ======================================================
# 3️⃣ CONFIRM ORDER (APPLY QTY + DISCOUNT + GENERATE BILL)
# ======================================================
@api_view(['POST'])
def api_confirm_order(request, order_id):
    """
    Confirms order, updates quantities & discounts,
    generates bill using generate_bill_from_order()
    """

    order = get_object_or_404(CustomerOrder, id=order_id)

    quantities = request.data.get("quantities", [])

    try:
        with transaction.atomic():

            # Update each order item
            for q in quantities:
                item_id = q.get("item_id")
                quantity = q.get("quantity", 0)
                discount = q.get("discount", 0)

                if item_id is None:
                    continue

                try:
                    order_item = order.items.get(id=item_id)
                except CustomerOrderItem.DoesNotExist:
                    continue

                order_item.requested_quantity = int(quantity)
                order_item.discount = Decimal(str(discount)) if discount else Decimal("0.00")
                order_item.discount_total = order_item.discount * order_item.requested_quantity
                order_item.requested_total = (
                    order_item.requested_price * order_item.requested_quantity
                ) - order_item.discount_total

                order_item.save()

            # Recalculate order total
            total_amount = sum(
                (oi.requested_total or Decimal("0.00"))
                for oi in order.items.all()
            )

            order.total_amount = total_amount
            order.status = "confirmed"
            order.save()

            # Generate bill
            bill = generate_bill_from_order(order)

            return Response({
                "success": True,
                "message": f"Order confirmed and bill generated",
                "bill_id": bill.id,
                "invoice_number": bill.invoice_number
            })

    except Exception as e:
        return Response({
            "success": False,
            "error": str(e)
        }, status=400)


# ======================================================
# 4️⃣ REJECT ORDER
# ======================================================
@api_view(['POST'])
def api_reject_order(request, order_id):
    """
    Rejects a pending order
    """

    order = get_object_or_404(CustomerOrder, id=order_id)

    order.status = "rejected"
    order.save()

    return Response({
        "success": True,
        "message": "Order rejected successfully"
    })
