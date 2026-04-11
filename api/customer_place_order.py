from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from customer_portal.models import CustomerOrder, CustomerOrderItem
from milk_agency.models import Item
from milk_agency.order_pricing import get_customer_unit_price, get_delivery_charge_amount
from milk_agency.paytm import initiate_order_transaction
from milk_agency.push_notifications import notify_admin_order_placed, notify_admin_order_updated


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def place_order_api(request):
    customer = request.user
    items = request.data.get("items", [])
    today = timezone.localdate()
    delivery_date_raw = request.data.get("delivery_date")
    delivery_address = str(request.data.get("delivery_address") or "").strip()
    payment_method = str(request.data.get("payment_method") or "").strip().upper() or "COD"

    if not isinstance(items, list) or not items:
        return Response({"success": False, "message": "No items selected"}, status=400)

    try:
        delivery_date = (
            timezone.datetime.strptime(delivery_date_raw, "%Y-%m-%d").date()
            if delivery_date_raw
            else today
        )
    except ValueError:
        return Response({"success": False, "message": "Invalid delivery_date"}, status=400)

    try:
        with transaction.atomic():
            order = CustomerOrder.objects.filter(
                customer=customer,
                delivery_date=delivery_date,
                status__in=["pending", "payment_pending"],
            ).first()
            created_new = order is None

            if not order:
                order_number = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                order = CustomerOrder.objects.create(
                    order_number=order_number,
                    order_date=today,
                    delivery_date=delivery_date,
                    delivery_address=delivery_address,
                    customer=customer,
                    created_by=customer,
                    payment_method=payment_method,
                    payment_status="pending",
                )
            else:
                order_number = order.order_number
                order.items.all().delete()
                order.delivery_date = delivery_date
                if delivery_address:
                    order.delivery_address = delivery_address
                order.payment_method = payment_method

            total_amount = 0

            for item_data in items:
                item_id = item_data.get("item_id")
                qty = int(item_data.get("quantity", 0))

                item = get_object_or_404(Item, id=item_id)
                price = get_customer_unit_price(item, customer)

                if qty <= 0 or price <= 0:
                    return Response({"success": False, "message": "Invalid item data"}, status=400)

                line_total = qty * price
                CustomerOrderItem.objects.create(
                    order=order,
                    item=item,
                    requested_quantity=qty,
                    requested_price=price,
                    approved_quantity=qty,
                    approved_price=price,
                    requested_total=line_total,
                )
                total_amount += line_total

            order.delivery_charge = get_delivery_charge_amount(
                customer=customer,
                address=order.delivery_address or delivery_address,
            )
            order.total_amount = total_amount
            order.approved_total_amount = total_amount
            requires_online_payment = (
                str(getattr(customer, "user_type", "") or "").lower() == "user"
                and payment_method not in ("COD", "CASH")
            )
            order.status = "payment_pending" if requires_online_payment else "pending"
            order.save()
            notifier = notify_admin_order_placed if created_new else notify_admin_order_updated
            transaction.on_commit(lambda order_id=order.id, notify_func=notifier: notify_func(CustomerOrder.objects.select_related("customer").get(pk=order_id)))

            payment_payload = None
            if requires_online_payment:
                try:
                    payment_payload = initiate_order_transaction(order)
                except Exception as exc:
                    order.payment_status = "failed"
                    order.status = "rejected"
                    order.save(update_fields=["payment_status", "status", "updated_at"])
                    return Response(
                        {
                            "success": False,
                            "message": f"Unable to initiate payment: {exc}",
                            "order_id": order.id,
                            "order_number": order_number,
                        },
                        status=502,
                    )

            return Response(
                {
                    "success": True,
                    "order_id": order.id,
                    "order_number": order_number,
                    "delivery_date": str(order.delivery_date),
                    "delivery_charge": float(order.delivery_charge or 0),
                    "grand_total": float((order.total_amount or 0) + (order.delivery_charge or 0)),
                    "status": order.status,
                    "payment_status": order.payment_status,
                    "payment_order_id": payment_payload["payment_order_id"] if payment_payload else order.gateway_order_id,
                    "txnToken": payment_payload["txnToken"] if payment_payload else "",
                    "gateway": "PAYTM" if payment_payload else "",
                    "message": "Order updated successfully",
                }
            )

    except Exception as exc:
        return Response({"success": False, "message": str(exc)}, status=500)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def customer_current_day_order_api(request):
    customer = request.user
    today = timezone.localdate()

    orders = (
        CustomerOrder.objects.filter(customer=customer, delivery_date=today)
        .prefetch_related("items__item")
        .order_by("-created_at")
    )

    if not orders.exists():
        return Response(
            {"message": "No orders found for today", "customer_id": customer.id, "customer_name": customer.name},
            status=404,
        )

    orders_data = []
    for order in orders:
        order_data = {
            "order_id": order.id,
            "order_number": order.order_number,
            "total_amount": float(order.total_amount),
            "approved_total_amount": float(order.approved_total_amount or 0),
            "delivery_charge": float(order.delivery_charge or 0),
            "grand_total": float((order.total_amount or 0) + (order.delivery_charge or 0)),
            "status": order.status,
            "order_date": order.order_date.strftime("%Y-%m-%d"),
            "delivery_date": order.delivery_date.strftime("%Y-%m-%d"),
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "delivery_address": order.delivery_address,
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

    return Response({"date": str(today), "orders": orders_data}, status=200)
