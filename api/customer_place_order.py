from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from milk_agency.models import Item
from customer_portal.models import CustomerOrder, CustomerOrderItem


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def place_order_api(request):
    """
    ANDROID PLACE ORDER API
    Creates ONLY ONE order per day.
    If order already exists -> update it.
    """

    customer = request.user
    items = request.data.get("items", [])
    today = timezone.localdate()

    if not isinstance(items, list) or not items:
        return Response(
            {"success": False, "message": "No items selected"},
            status=400
        )

    try:
        with transaction.atomic():

            # 🔎 CHECK TODAY ORDER
            order = CustomerOrder.objects.filter(
                customer=customer,
                order_date__date=today
            ).first()

            # 🆕 CREATE ORDER IF NOT EXISTS
            if not order:
                order_number = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}"

                order = CustomerOrder.objects.create(
                    order_number=order_number,
                    customer=customer,
                    created_by=customer,
                )

            else:
                order_number = order.order_number

                # OPTIONAL: clear previous items
                order.items.all().delete()

            total_amount = 0

            for i in items:
                item_id = i.get("item_id")
                qty = int(i.get("quantity", 0))

                item = get_object_or_404(Item, id=item_id)
                price = item.selling_price

                if qty <= 0 or price <= 0:
                    return Response(
                        {"success": False, "message": "Invalid item data"},
                        status=400
                    )

                line_total = qty * price

                # CREATE ORDER ITEM
                CustomerOrderItem.objects.create(
                    order=order,
                    item=item,
                    requested_quantity=qty,
                    requested_price=price,
                    requested_total=line_total
                )

                total_amount += line_total

            # UPDATE TOTAL
            order.total_amount = total_amount
            order.approved_total_amount = total_amount
            order.save()

            return Response({
                "success": True,
                "order_number": order_number,
                "message": "Order updated successfully"
            })

    except Exception as e:
        return Response(
            {"success": False, "message": str(e)},
            status=500
        )

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def customer_current_day_order_api(request):
    customer = request.user
    today = timezone.localdate()

    orders = (
        CustomerOrder.objects.filter(customer=customer, status="pending")
        .prefetch_related("items__item")
        .order_by("-order_date")
    )

    if not orders.exists():
        return Response({
            "message": "No orders found for today",
            "customer_id": customer.id,
            "customer_name": customer.name
        }, status=404)

    orders_data = []
    for order in orders:
        order_data = {
            "order_number": order.order_number,
            "total_amount": float(order.total_amount),
            "status": order.status,
            "order_date": timezone.localtime(order.order_date).strftime("%Y-%m-%d %H:%M:%S"),
            "created_at": timezone.localtime(order.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            "items": [],
        }

        for item in order.items.all():
            order_data["items"].append(
                {
                    "item_id": item.item.id,
                    "item_name": item.item.name,
                    "requested_quantity": item.requested_quantity,
                    "requested_price": float(item.requested_price),
                    "requested_total": float(item.requested_total),
                }
            )

        orders_data.append(order_data)

    return Response(
        {
            "date": str(today),
            "orders": orders_data,
        },
        status=200,
    )

