"""
Order creation/update/delete + pending listing for customer (user portal / Android).
Uses CustomerOrder (with devivery_date) and CustomerOrderItem.
"""
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Mapping, Optional, Tuple

from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from customer_portal.models import CustomerOrder, CustomerOrderItem
from milk_agency.models import Customer, Item


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _build_address(customer: Customer) -> str:
    parts = [
        getattr(customer, "flat_number", "") or "",
        getattr(customer, "area", "") or "",
        getattr(customer, "city", "") or "",
        getattr(customer, "state", "") or "",
        getattr(customer, "pin_code", "") or "",
    ]
    cleaned = [p.strip() for p in parts if p.strip()]
    return ", ".join(cleaned) if cleaned else "Not provided"


def _parse_delivery_date(
    raw: Optional[str],
    allow_past_if_same: Optional[datetime.date] = None,
) -> Tuple[datetime.date, bool]:
    """
    Returns (delivery_date, is_prebooking)
    - None/"" => today (not prebooking)
    - YYYY-MM-DD => that date, must not be in the past
    """
    today = timezone.localdate()
    if not raw:
        return today, False
    delivery_date = datetime.strptime(raw, "%Y-%m-%d").date()
    if delivery_date < today and not (
        allow_past_if_same and delivery_date == allow_past_if_same
    ):
        raise ValueError("Delivery date cannot be in the past")
    return delivery_date, delivery_date != today


def _coerce_items(items: Iterable[Mapping]) -> Iterable[Mapping]:
    if not isinstance(items, list) or not items:
        raise ValueError("No items selected")
    return items


def _create_line(order: CustomerOrder, entry: Mapping) -> Decimal:
    item_id = entry.get("item_id")
    qty = int(entry.get("quantity", 0))
    price = entry.get("price")

    if qty <= 0:
        raise ValueError("Quantity must be greater than zero")

    item = get_object_or_404(Item, id=item_id)
    unit_price = Decimal(str(price if price is not None else item.selling_price))
    line_total = unit_price * qty

    CustomerOrderItem.objects.create(
        order=order,
        item=item,
        requested_quantity=qty,
        requested_price=unit_price,
        requested_total=line_total,
    )
    return line_total


# -------------------------------------------------------------------
# Core operations
# -------------------------------------------------------------------
def create_or_replace_order(
    customer: Customer,
    items: Iterable[Mapping],
    delivery_date_str: Optional[str] = None,
) -> CustomerOrder:
    items = _coerce_items(items)
    delivery_date, _ = _parse_delivery_date(delivery_date_str)

    with transaction.atomic():
        order = CustomerOrder.objects.filter(
            customer=customer, delivery_date=delivery_date
        ).first()

        if order:
            order.items.all().delete()
        else:
            order_number = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            order = CustomerOrder.objects.create(
                order_number=order_number,
                customer=customer,
                created_by=customer,
                delivery_date=delivery_date,
                delivery_address=_build_address(customer),
                status="pending",
            )

        total = Decimal("0")
        for entry in items:
            total += _create_line(order, entry)

        order.total_amount = total
        order.approved_total_amount = total
        order.save(update_fields=["total_amount", "approved_total_amount"])
        return order


def edit_order(
    customer: Customer,
    order_id: int,
    items: Iterable[Mapping],
    delivery_date_str: Optional[str] = None,
) -> CustomerOrder:
    items = _coerce_items(items)

    with transaction.atomic():
        order = get_object_or_404(CustomerOrder, id=order_id, customer=customer)
        # Allow editing an existing order even if its delivery date is now in the past,
        # as long as the client does not move it further back in time.
        delivery_date, _ = _parse_delivery_date(
            delivery_date_str, allow_past_if_same=order.delivery_date
        )
        order.delivery_date = delivery_date
        order.items.all().delete()

        total = Decimal("0")
        for entry in items:
            total += _create_line(order, entry)

        order.total_amount = total
        order.approved_total_amount = total
        order.save(update_fields=["delivery_date", "total_amount", "approved_total_amount"])
        return order


def delete_order(customer: Customer, order_id: int) -> bool:
    deleted, _ = CustomerOrder.objects.filter(id=order_id, customer=customer).delete()
    return deleted > 0


# -------------------------------------------------------------------
# API endpoints (token protected)
# -------------------------------------------------------------------
@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_create_order(request):
    if not request.user or not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided."}, status=401)
    try:
        order = create_or_replace_order(
            customer=request.user,
            items=request.data.get("items", []),
            delivery_date_str=request.data.get("delivery_date"),
        )
        return Response({
            "success": True,
            "order_number": order.order_number,
            "delivery_date": str(order.delivery_date),
            "message": "Order saved successfully",
        })
    except Exception as e:
        return Response({"success": False, "message": str(e)}, status=400)


@api_view(["PUT", "PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_edit_order(request, order_id: int):
    if not request.user or not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided."}, status=401)
    try:
        order = edit_order(
            customer=request.user,
            order_id=order_id,
            items=request.data.get("items", []),
            delivery_date_str=request.data.get("delivery_date"),
        )
        return Response({
            "success": True,
            "order_number": order.order_number,
            "delivery_date": str(order.delivery_date),
            "message": "Order updated successfully",
        })
    except Exception as e:
        return Response({"success": False, "message": str(e)}, status=400)


@api_view(["DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_delete_order(request, order_id: int):
    if not request.user or not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided."}, status=401)
    if delete_order(request.user, order_id):
        return Response({"success": True, "message": "Order deleted"})
    return Response({"success": False, "message": "Order not found"}, status=404)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_pending_orders(request):
    if not request.user or not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided."}, status=401)
    orders = (
        CustomerOrder.objects.filter(customer=request.user, status="pending")
        .prefetch_related(
            Prefetch(
                "items",
                queryset=CustomerOrderItem.objects.select_related("item"),
            )
        )
        .order_by("delivery_date", "-order_date", "-created_at")
    )

    data = []
    for order in orders:
        data.append({
            "order_id": order.id,
            "order_number": order.order_number,
            "delivery_date": str(order.delivery_date),
            "order_date": str(order.order_date),
            "total_amount": float(order.total_amount),
            "items": [
                {
                    "item_id": oi.item.id,
                    "item_name": oi.item.name,
                    "quantity": oi.requested_quantity,
                    "price": float(oi.requested_price),
                    "line_total": float(oi.requested_total),
                }
                for oi in order.items.all()
            ],
        })

    return Response({"orders": data, "count": len(data)})
