from django.apps import apps
from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from customer_portal.models import CustomerOrder


def _order_delivery_model():
    return apps.get_model("milk_agency", "OrderDelivery")


def _subscription_delivery_model():
    return apps.get_model("milk_agency", "SubscriptionDelivery")


def _subscription_order_model():
    return apps.get_model("milk_agency", "SubscriptionOrder")


class SubscriptionDeliveryFallback:
    def __init__(self, subscription_order, status):
        self.id = None
        self.subscription_order = subscription_order
        self.status = status


def _model_is_queryable(model):
    try:
        table_names = connection.introspection.table_names()
        if model._meta.db_table not in table_names:
            return False

        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, model._meta.db_table)
        db_columns = {col.name for col in description}
        model_columns = {
            field.column
            for field in model._meta.local_concrete_fields
            if getattr(field, "column", None)
        }
        return model_columns.issubset(db_columns)
    except Exception:
        return False


def _serialize_order_delivery(od):
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


def _serialize_subscription_delivery(sd):
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
    OrderDelivery = _order_delivery_model()
    SubscriptionDelivery = _subscription_delivery_model()
    SubscriptionOrder = _subscription_order_model()
    has_subscription_delivery_table = _model_is_queryable(SubscriptionDelivery)

    pending_orders = OrderDelivery.objects.filter(
        order__delivery_date=today,
        status__in=["pending", "out_for_delivery"]
    ).select_related("order", "order__customer")

    completed_orders = OrderDelivery.objects.filter(
        order__delivery_date=today,
        status="delivered"
    ).select_related("order", "order__customer")

    if has_subscription_delivery_table:
        pending_subs = SubscriptionDelivery.objects.filter(
            subscription_order__date=today,
            status__in=["pending", "out_for_delivery"]
        ).select_related("subscription_order__customer", "subscription_order__item")

        completed_subs = SubscriptionDelivery.objects.filter(
            subscription_order__date=today,
            status="delivered"
        ).select_related("subscription_order__customer", "subscription_order__item")
    else:
        pending_subs = [
            SubscriptionDeliveryFallback(subscription_order=obj, status="pending")
            for obj in SubscriptionOrder.objects.filter(date=today, delivered=False).select_related("customer", "item")
        ]
        completed_subs = [
            SubscriptionDeliveryFallback(subscription_order=obj, status="delivered")
            for obj in SubscriptionOrder.objects.filter(date=today, delivered=True).select_related("customer", "item")
        ]

    return Response({
        "pending": [_serialize_order_delivery(o) for o in pending_orders] +
                   [_serialize_subscription_delivery(s) for s in pending_subs],
        "completed": [_serialize_order_delivery(o) for o in completed_orders] +
                     [_serialize_subscription_delivery(s) for s in completed_subs],
    })


def _update_order_delivery(obj, data, user):
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


def _update_subscription_delivery(obj, data, user):
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

    OrderDelivery = _order_delivery_model()
    SubscriptionDelivery = _subscription_delivery_model()
    SubscriptionOrder = _subscription_order_model()
    has_subscription_delivery_table = _model_is_queryable(SubscriptionDelivery)

    try:
        if delivery_type == "order":
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
            if has_subscription_delivery_table:
                if delivery_id:
                    obj = SubscriptionDelivery.objects.select_related("subscription_order").get(id=delivery_id)
                else:
                    sub_order_id = data.get("subscription_order_id")
                    if not sub_order_id:
                        return Response({"success": False, "message": "subscription_order_id is required to create delivery"}, status=400)
                    so = SubscriptionOrder.objects.get(id=sub_order_id)
                    obj, _ = SubscriptionDelivery.objects.get_or_create(subscription_order=so)
                _update_subscription_delivery(obj, data, request.user)
                return Response({"success": True, "message": "Subscription delivery updated", "delivery_id": obj.id})
            else:
                sub_order_id = data.get("subscription_order_id")
                if delivery_id and not sub_order_id:
                    return Response({"success": False, "message": "subscription_order_id is required for this server schema"}, status=400)
                if not sub_order_id:
                    return Response({"success": False, "message": "subscription_order_id is required to update delivery"}, status=400)
                so = SubscriptionOrder.objects.get(id=sub_order_id)
                status = data.get("status")
                if status == "delivered":
                    so.delivered = True
                elif status in ("pending", "out_for_delivery", "skipped", "failed"):
                    so.delivered = False
                so.save(update_fields=["delivered"])
                return Response({"success": True, "message": "Subscription delivery updated", "delivery_id": None})
    except (OrderDelivery.DoesNotExist, SubscriptionDelivery.DoesNotExist):
        return Response({"success": False, "message": "Delivery not found"}, status=404)
    except CustomerOrder.DoesNotExist:
        return Response({"success": False, "message": "Order not found"}, status=404)
    except SubscriptionOrder.DoesNotExist:
        return Response({"success": False, "message": "Subscription order not found"}, status=404)
    except Exception as e:
        return Response({"success": False, "message": str(e)}, status=400)
    
