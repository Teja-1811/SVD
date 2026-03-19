from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from milk_agency.models import OrderDelivery, SubscriptionDelivery


def _serialize_order_delivery(od: OrderDelivery):
    return {
        "type": "order",
        "id": od.id,
        "order_number": od.order.order_number,
        "customer_name": od.order.customer.name,
        "delivery_date": str(od.order.delivery_date) if hasattr(od.order, "delivery_date") else str(od.order.order_date),
        "status": od.status,
        "total_amount": float(od.order.total_amount),
        "address": getattr(od.order, "delivery_address", ""),
    }


def _serialize_subscription_delivery(sd: SubscriptionDelivery):
    return {
        "type": "subscription",
        "id": sd.id,
        "customer_name": sd.subscription_order.customer.name,
        "plan_item": sd.subscription_order.item.name,
        "date": str(sd.subscription_order.date),
        "status": sd.status,
        "quantity": sd.subscription_order.quantity,
    }


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delivery_today_list(request):
    """
    Delivery agent view:
    - pending: pending + out_for_delivery for today
    - completed: delivered for today
    """
    today = timezone.localdate()

    pending_orders = OrderDelivery.objects.filter(
        order__delivery_date=today,
        status__in=["pending", "out_for_delivery"]
    ).select_related("order", "order__customer")

    completed_orders = OrderDelivery.objects.filter(
        order__delivery_date=today,
        status="delivered"
    ).select_related("order", "order__customer")

    pending_subs = SubscriptionDelivery.objects.filter(
        subscription_order__date=today,
        status__in=["pending", "out_for_delivery"]
    ).select_related("subscription_order__customer", "subscription_order__item")

    completed_subs = SubscriptionDelivery.objects.filter(
        subscription_order__date=today,
        status="delivered"
    ).select_related("subscription_order__customer", "subscription_order__item")

    return Response({
        "pending": [_serialize_order_delivery(o) for o in pending_orders] +
                   [_serialize_subscription_delivery(s) for s in pending_subs],
        "completed": [_serialize_order_delivery(o) for o in completed_orders] +
                     [_serialize_subscription_delivery(s) for s in completed_subs],
    })


def _update_order_delivery(obj: OrderDelivery, data, user):
    status = data.get("status")
    if status:
        obj.status = status
    if "eta" in data:
        obj.eta = data.get("eta")  # expect ISO string; DRF parser may convert
    if "delivered_at" in data:
        obj.delivered_at = data.get("delivered_at")
    if "delivered_amount" in data:
        obj.delivered_amount = data.get("delivered_amount") or 0
    if "notes" in data:
        obj.notes = data.get("notes") or ""
    obj.delivered_by = user
    obj.save()


def _update_subscription_delivery(obj: SubscriptionDelivery, data, user):
    status = data.get("status")
    if status:
        obj.status = status
    if "eta" in data:
        obj.eta = data.get("eta")
    if "delivered_at" in data:
        obj.delivered_at = data.get("delivered_at")
    if "notes" in data:
        obj.notes = data.get("notes") or ""
    obj.delivered_by = user
    obj.save()


@api_view(["PATCH", "PUT"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delivery_update(request):
    """
    Update delivery status for either order or subscription.
    Accepts either an existing delivery id OR creates one if only target order/subscription is provided.
    Body example:
    {
      "type": "order" | "subscription",
      "delivery_id": <optional delivery id>,
      "order_id": <optional, required when creating order delivery>,
      "subscription_order_id": <optional, required when creating subscription delivery>,
      "status": "...",
      "delivered_amount": 123.45,   # orders only
      "eta": "2026-03-19T12:30:00Z",
      "delivered_at": "2026-03-19T13:00:00Z",
      "notes": "left at door"
    }
    """
    data = request.data or {}
    delivery_type = data.get("type")
    delivery_id = data.get("delivery_id") or data.get("id")

    if delivery_type not in ("order", "subscription"):
        return Response({"success": False, "message": "type is required (order|subscription)"}, status=400)

    try:
        if delivery_type == "order":
            from customer_portal.models import CustomerOrder
            if delivery_id:
                obj = OrderDelivery.objects.select_related("order").get(id=delivery_id)
            else:
                order_id = data.get("order_id")
                if not order_id:
                    return Response({"success": False, "message": "order_id is required to create delivery"}, status=400)
                order = CustomerOrder.objects.get(id=order_id)
                obj, _ = OrderDelivery.objects.get_or_create(order=order)
            _update_order_delivery(obj, data, request.user)
            return Response({"success": True, "message": "Order delivery updated", "delivery_id": obj.id})
        else:
            if delivery_id:
                obj = SubscriptionDelivery.objects.select_related("subscription_order").get(id=delivery_id)
            else:
                sub_order_id = data.get("subscription_order_id")
                if not sub_order_id:
                    return Response({"success": False, "message": "subscription_order_id is required to create delivery"}, status=400)
                from milk_agency.models import SubscriptionOrder
                so = SubscriptionOrder.objects.get(id=sub_order_id)
                obj, _ = SubscriptionDelivery.objects.get_or_create(subscription_order=so)
            _update_subscription_delivery(obj, data, request.user)
            return Response({"success": True, "message": "Subscription delivery updated", "delivery_id": obj.id})
    except (OrderDelivery.DoesNotExist, SubscriptionDelivery.DoesNotExist):
        return Response({"success": False, "message": "Delivery not found"}, status=404)
    except CustomerOrder.DoesNotExist:
        return Response({"success": False, "message": "Order not found"}, status=404)
    except Exception as e:
        return Response({"success": False, "message": str(e)}, status=400)
    