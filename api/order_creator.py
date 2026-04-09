"""
Order creation/update/delete + pending listing for customer (user portal / Android).
Uses CustomerOrder (with devivery_date) and CustomerOrderItem.
"""
from datetime import datetime, timedelta
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
from milk_agency.order_pricing import get_customer_unit_price, get_delivery_charge_amount

ACTIVE_ORDER_STATUSES = ("payment_pending", "pending", "confirmed", "processing", "ready")
USER_COMPANY_NAME = "Dodla"


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

    try:
        delivery_date = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Invalid delivery date.") from exc

    if delivery_date < today and not (
        allow_past_if_same and delivery_date == allow_past_if_same
    ):
        raise ValueError("Delivery date cannot be in the past")
    return delivery_date, delivery_date != today


def minimum_prebook_date():
    return timezone.localdate() + timedelta(days=2)


def _available_items(*, include_out_of_stock=False):
    queryset = Item.objects.select_related("company").filter(
        frozen=False,
        company__name__iexact=USER_COMPANY_NAME,
    )
    if not include_out_of_stock:
        queryset = queryset.filter(stock_quantity__gt=0)
    return queryset


def _coerce_items(items: Iterable[Mapping], *, is_prebooking: bool) -> Iterable[Mapping]:
    if not isinstance(items, list) or not items:
        raise ValueError("No items selected")

    normalized = {}
    valid_items = {
        item.id: item
        for item in _available_items(include_out_of_stock=True)
    }

    for entry in items:
        try:
            item_id = int(entry.get("item_id"))
            quantity = int(entry.get("quantity", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid product selection.") from exc

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")
        if item_id not in valid_items:
            raise ValueError("One or more selected products are unavailable.")

        normalized.setdefault(item_id, {"item": valid_items[item_id], "quantity": 0})
        normalized[item_id]["quantity"] += quantity

    if not is_prebooking:
        for entry in normalized.values():
            item = entry["item"]
            quantity = entry["quantity"]
            if item.stock_quantity <= 0:
                raise ValueError(f"{item.name} is out of stock.")
            if quantity > item.stock_quantity:
                raise ValueError(f"Only {item.stock_quantity} unit(s) available for {item.name}.")

    return list(normalized.values())


def _create_line(order: CustomerOrder, entry: Mapping) -> Decimal:
    item = entry["item"]
    qty = int(entry["quantity"])
    unit_price = get_customer_unit_price(item, order.customer)
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
    *,
    initial_status: str = "pending",
    payment_method: str = "",
) -> CustomerOrder:
    delivery_date, is_prebooking = _parse_delivery_date(delivery_date_str)
    if is_prebooking and delivery_date < minimum_prebook_date():
        raise ValueError("Pre-booking is allowed only from 2 days ahead.")
    items = _coerce_items(items, is_prebooking=is_prebooking)

    with transaction.atomic():
        order = CustomerOrder.objects.filter(
            customer=customer,
            delivery_date=delivery_date,
            status=initial_status,
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
                status=initial_status,
                payment_method=payment_method or "",
            )

        total = Decimal("0")
        for entry in items:
            total += _create_line(order, entry)

        order.delivery_charge = get_delivery_charge_amount(customer=customer, address=order.delivery_address)
        order.total_amount = total
        order.approved_total_amount = total
        order.payment_method = payment_method or order.payment_method
        order.payment_status = "pending" if initial_status == "payment_pending" else order.payment_status
        order.save(update_fields=["total_amount", "approved_total_amount", "delivery_charge", "payment_method", "payment_status"])
        return order


def edit_order(
    customer: Customer,
    order_id: int,
    items: Iterable[Mapping],
    delivery_date_str: Optional[str] = None,
) -> CustomerOrder:
    with transaction.atomic():
        order = get_object_or_404(CustomerOrder, id=order_id, customer=customer)
        # Allow editing an existing order even if its delivery date is now in the past,
        # as long as the client does not move it further back in time.
        delivery_date, is_prebooking = _parse_delivery_date(
            delivery_date_str, allow_past_if_same=order.delivery_date
        )
        if is_prebooking and delivery_date < minimum_prebook_date():
            raise ValueError("Pre-booking is allowed only from 2 days ahead.")
        items = _coerce_items(items, is_prebooking=is_prebooking)
        order.delivery_date = delivery_date
        order.items.all().delete()

        total = Decimal("0")
        for entry in items:
            total += _create_line(order, entry)

        order.delivery_charge = get_delivery_charge_amount(customer=customer, address=order.delivery_address)
        order.total_amount = total
        order.approved_total_amount = total
        order.save(update_fields=["delivery_date", "total_amount", "approved_total_amount", "delivery_charge"])
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
            "is_prebooking": order.delivery_date > timezone.localdate(),
            "message": "Pre-booking saved successfully." if order.delivery_date > timezone.localdate() else "Order saved successfully.",
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
        CustomerOrder.objects.filter(
            customer=request.user,
            status__in=ACTIVE_ORDER_STATUSES,
        )
        .prefetch_related(
            Prefetch(
                "items",
                queryset=CustomerOrderItem.objects.select_related("item"),
            )
        )
        .order_by("-delivery_date", "-order_date", "-created_at")
    )

    data = []
    for order in orders:
        data.append({
            "order_id": order.id,
            "order_number": order.order_number,
            "status": order.status,
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
