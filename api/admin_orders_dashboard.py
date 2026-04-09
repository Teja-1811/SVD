import json
from decimal import Decimal

from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from customer_portal.models import CustomerOrder, CustomerOrderItem
from milk_agency.order_pricing import get_customer_unit_price
from milk_agency.views_bills import generate_bill_from_order


# ======================================================
# 1️⃣ ADMIN ORDERS DASHBOARD (PENDING ORDERS)
# ======================================================
@api_view(['GET'])
def api_admin_orders_dashboard(request):

    status_filter = request.GET.get("status", "").strip().lower()
    pending_orders = CustomerOrder.objects.filter(
        status__in=["pending", "payment_pending", "confirmed"]
    ).select_related("customer", "approved_by", "bill").prefetch_related("items__item").order_by("delivery_date", "-order_date")

    if status_filter:
        pending_orders = pending_orders.filter(status=status_filter)

    orders = []

    for order in pending_orders:
        grand_total = float((order.total_amount or 0) + (order.delivery_charge or 0))
        orders.append({
            "order_id": order.id,
            "order_number": order.order_number,
            "order_date": str(order.order_date),
            "delivery_date": str(order.delivery_date),
            "customer_id": order.customer.id if order.customer else None,
            "customer_name": order.customer.name if order.customer else "",
            "phone": order.customer.phone if order.customer else "",
            "status": order.status,
            "total_amount": float(order.total_amount or 0),
            "approved_total_amount": float(order.approved_total_amount or 0),
            "delivery_charge": float(order.delivery_charge or 0),
            "grand_total": grand_total,
            "payment_status": order.payment_status,
            "payment_method": order.payment_method,
            "payment_reference": order.payment_reference,
            "bill_id": order.bill_id,
            "items": [
                {
                    "order_item_id": oi.id,
                    "item_id": oi.item.id,
                    "item_name": oi.item.name,
                    "requested_price": float(oi.requested_price),
                    "requested_quantity": oi.requested_quantity,
                    "approved_quantity": oi.approved_quantity,
                    "approved_price": float(oi.approved_price or 0),
                    "discount": float(oi.discount or 0),
                    "discount_total": float(oi.discount_total or 0),
                    "requested_total": float(oi.requested_total or 0),
                    "approved_total": float(oi.approved_total or 0),
                    "admin_notes": oi.admin_notes or "",
                }
                for oi in order.items.all()
            ]
        })

    return Response({
        "summary": {
            "total_pending": pending_orders.count(),
            "payment_pending": pending_orders.filter(status="payment_pending").count(),
            "review_pending": pending_orders.filter(status="pending").count(),
            "confirmed": pending_orders.filter(status="confirmed").count(),
        },
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
        "order_number": order.order_number,
        "order_date": str(order.order_date),
        "delivery_date": str(order.delivery_date),
        "customer_name": order.customer.name if order.customer else "",
        "customer_id": order.customer_id,
        "phone": order.customer.phone if order.customer else "",
        "status": order.status,
        "total_amount": float(order.total_amount or 0),
        "approved_total_amount": float(order.approved_total_amount or 0),
        "delivery_charge": float(order.delivery_charge or 0),
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
        "payment_reference": order.payment_reference,
        "delivery_address": order.delivery_address,
        "bill_id": order.bill_id,
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
