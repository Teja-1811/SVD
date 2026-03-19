import json
from decimal import Decimal

from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.db import transaction
from django.shortcuts import get_object_or_404

from customer_portal.models import CustomerOrder, CustomerOrderItem
from milk_agency.order_pricing import get_customer_unit_price
from milk_agency.views_bills import generate_bill_from_order


# ======================================================
# 1️⃣ ADMIN ORDERS DASHBOARD (PENDING ORDERS)
# ======================================================
@api_view(['GET'])
def api_admin_orders_dashboard(request):

    pending_orders = CustomerOrder.objects.filter(
        status="pending"
    ).select_related("customer").prefetch_related("items__item").order_by("-order_date")

    orders = []

    for order in pending_orders:
        orders.append({
            "order_id": order.id,
            "order_date": str(order.order_date),
            "customer_id": order.customer.id if order.customer else None,
            "customer_name": order.customer.name if order.customer else "",
            "total_amount": float(order.total_amount or 0),
            "items": [
                {
                    "item_id": oi.item.id,
                    "item_name": oi.item.name,
                    "requested_price": float(oi.requested_price),
                    "requested_quantity": oi.requested_quantity,
                    "discount": float(oi.discount or 0),
                    "discount_total": float(oi.discount_total or 0),
                    "requested_total": float(oi.requested_total or 0)
                }
                for oi in order.items.all()
            ]
        })

    return Response({
        "total_pending": pending_orders.count(),
        "orders": orders
    })


# ======================================================
# 2️⃣ ORDER DETAILS
# ======================================================
@api_view(['GET'])
def api_order_detail(request, order_id):

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
# 3️⃣ CONFIRM ORDER (SAFE VERSION)
# ======================================================
@api_view(['POST'])
def api_confirm_order(request, order_id):

    order = get_object_or_404(CustomerOrder, id=order_id)

    # 🔴 Prevent duplicate confirmation
    if order.status != "pending":
        return Response({
            "success": False,
            "message": "Order already processed"
        }, status=400)

    quantities = request.data.get("quantities", [])

    try:
        with transaction.atomic():
            # ---- Update order items ----
            for q in quantities:
                item_id = q.get("item_id")
                quantity = q.get("quantity", 0)
                discount = q.get("discount", 0)

                if item_id is None:
                    continue

                order_item = order.items.filter(id=item_id).first()
                if not order_item:
                    continue

                unit_price = get_customer_unit_price(order_item.item, order.customer)
                discount_decimal = Decimal(str(discount)) if discount else Decimal("0.00")
                if discount_decimal < 0:
                    return Response({
                        "success": False,
                        "message": "Discount cannot be negative"
                    }, status=400)

                order_item.requested_quantity = int(quantity)
                order_item.requested_price = unit_price
                order_item.approved_quantity = int(quantity)
                order_item.approved_price = unit_price
                order_item.discount = discount_decimal
                order_item.discount_total = discount_decimal * order_item.requested_quantity
                order_item.requested_total = (
                    unit_price * order_item.requested_quantity
                ) - order_item.discount_total
                order_item.approved_total = order_item.requested_total
                order_item.save()

            # ---- Recalculate order total ----
            total_amount = sum(
                (oi.requested_total or Decimal("0.00"))
                for oi in order.items.all()
            )

            order.total_amount = total_amount
            order.status = "confirmed"
            order.save()

            # ---- Generate Bill ----
            bill = generate_bill_from_order(order)

            return Response({
                "success": True,
                "message": "Order confirmed and bill generated",
                "bill_id": bill.id,
                "invoice_number": bill.invoice_number
            })

    except Exception as e:
        return Response({
            "success": False,
            "error": str(e)
        }, status=400)


# ======================================================
# 4️⃣ REJECT ORDER (SAFE)
# ======================================================
@api_view(['POST'])
def api_reject_order(request, order_id):

    order = get_object_or_404(CustomerOrder, id=order_id)

    if order.status != "pending":
        return Response({
            "success": False,
            "message": "Only pending orders can be rejected"
        }, status=400)

    order.status = "rejected"
    order.save()

    return Response({
        "success": True,
        "message": "Order rejected successfully"
    })
