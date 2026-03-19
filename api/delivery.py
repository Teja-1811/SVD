from django.apps import apps
from django.db import connection
from django.db.models import Q
from datetime import datetime
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


class OrderDeliveryFallback:
    def __init__(self, order, status):
        self.id = None
        self.order = order
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


def _present_order_status(raw_status):
    return "out_for_delivery" if raw_status == "confirmed" else (raw_status or "pending")


def _clean_text(value):
    return str(value or "").strip().lower()


def _parse_filter_date(raw):
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _get_filters(request):
    raw_date = (request.GET.get("date") or "").strip()
    return {
        "q": _clean_text(request.GET.get("q")),
        "kind": (request.GET.get("kind") or "all").strip().lower(),
        "stage": (request.GET.get("stage") or "all").strip().lower(),
        "status": (request.GET.get("status") or "all").strip().lower(),
        "date_raw": raw_date,
        "date": _parse_filter_date(raw_date),
    }


def _matches_order_delivery(item, filters):
    display_status = _present_order_status(item.status)
    if filters["kind"] not in ("all", "order"):
        return False
    if filters["stage"] == "pending" and display_status == "delivered":
        return False
    if filters["stage"] == "delivered" and display_status != "delivered":
        return False
    if filters["status"] != "all" and display_status != filters["status"]:
        return False
    if filters["date"] and getattr(item.order, "delivery_date", None) != filters["date"]:
        return False
    if filters["q"]:
        haystack = " ".join([
            getattr(item.order, "order_number", ""),
            getattr(getattr(item.order, "customer", None), "name", ""),
            getattr(getattr(item.order, "customer", None), "phone", ""),
            getattr(item.order, "delivery_address", ""),
        ]).lower()
        if filters["q"] not in haystack:
            return False
    return True


def _matches_subscription_delivery(item, filters):
    if filters["kind"] not in ("all", "subscription"):
        return False
    if filters["stage"] == "pending" and item.status == "delivered":
        return False
    if filters["stage"] == "delivered" and item.status != "delivered":
        return False
    if filters["status"] != "all" and item.status != filters["status"]:
        return False
    if filters["date"] and getattr(item.subscription_order, "date", None) != filters["date"]:
        return False
    if filters["q"]:
        haystack = " ".join([
            getattr(getattr(item.subscription_order, "customer", None), "name", ""),
            getattr(getattr(item.subscription_order, "customer", None), "phone", ""),
            getattr(getattr(item.subscription_order, "item", None), "name", ""),
        ]).lower()
        if filters["q"] not in haystack:
            return False
    return True


def _serialize_order_delivery(od):
    delivery_charge = getattr(od.order, "delivery_charge", 0) or 0
    grand_total = float((od.order.total_amount or 0) + delivery_charge)
    status = _present_order_status(od.status)
    return {
        "type": "order",
        "id": od.id,
        "order_number": od.order.order_number,
        "order_id": od.order.id,
        "customer_name": od.order.customer.name,
        "delivery_date": str(od.order.delivery_date) if hasattr(od.order, "delivery_date") else str(od.order.order_date),
        "status": status,
        "status_label": status.replace("_", " ").title(),
        "total_amount": grand_total,
        "items_total": float(od.order.total_amount or 0),
        "delivery_charge": float(delivery_charge),
        "grand_total": grand_total,
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
    filters = _get_filters(request)
    today = filters["date"] or timezone.localdate()
    OrderDelivery = _order_delivery_model()
    SubscriptionDelivery = _subscription_delivery_model()
    SubscriptionOrder = _subscription_order_model()
    has_order_delivery_table = _model_is_queryable(OrderDelivery)
    has_subscription_delivery_table = _model_is_queryable(SubscriptionDelivery)

    if has_order_delivery_table:
        pending_orders = [
            OrderDeliveryFallback(
                order=order,
                status=(
                    _present_order_status(getattr(getattr(order, "delivery_tracking", None), "status", None))
                    if getattr(getattr(order, "delivery_tracking", None), "status", None)
                    else None
                ) or (
                    _present_order_status(order.status)
                    if getattr(order, "status", None)
                    else None
                )
                or "pending",
            )
            for order in (
                CustomerOrder.objects
                .select_related("customer")
                .filter(
                    delivery_date=today
                )
                .filter(
                    Q(status__in=["pending", "confirmed", "processing", "ready"]) |
                    Q(delivery_tracking__status__in=["pending", "out_for_delivery", "failed"])
                )
                .exclude(status__in=["rejected", "cancelled", "delivered"])
                .distinct()
                .order_by("delivery_date", "-order_date", "-created_at")
            )
        ]
        completed_orders = [
            OrderDeliveryFallback(
                order=order,
                status=(
                    _present_order_status(getattr(getattr(order, "delivery_tracking", None), "status", None))
                    if getattr(getattr(order, "delivery_tracking", None), "status", None)
                    else None
                ) or (
                    _present_order_status(order.status)
                    if getattr(order, "status", None)
                    else None
                ) or "delivered",
            )
            for order in (
                CustomerOrder.objects
                .select_related("customer")
                .filter(delivery_date=today)
                .filter(Q(status="delivered") | Q(delivery_tracking__status="delivered"))
                .distinct()
                .order_by("-delivery_date", "-updated_at")
            )
        ]
    else:
        pending_orders = [
            OrderDeliveryFallback(order=order, status=_present_order_status(order.status or "pending"))
            for order in (
                CustomerOrder.objects
                .select_related("customer")
                .filter(
                    delivery_date=today,
                    status__in=["pending", "confirmed", "processing", "ready"],
                )
                .exclude(status__in=["rejected", "cancelled", "delivered"])
                .order_by("delivery_date", "-order_date", "-created_at")
            )
        ]
        completed_orders = [
            OrderDeliveryFallback(order=order, status=_present_order_status("delivered"))
            for order in (
                CustomerOrder.objects
                .select_related("customer")
                .filter(delivery_date=today, status="delivered")
                .order_by("-delivery_date", "-updated_at")
            )
        ]

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

    pending_orders = [item for item in pending_orders if _matches_order_delivery(item, filters)]
    completed_orders = [item for item in completed_orders if _matches_order_delivery(item, filters)]
    pending_subs = [item for item in pending_subs if _matches_subscription_delivery(item, filters)]
    completed_subs = [item for item in completed_subs if _matches_subscription_delivery(item, filters)]

    return Response({
        "date": str(today),
        "filters": {
            "q": filters["q"],
            "kind": filters["kind"],
            "stage": filters["stage"],
            "status": filters["status"],
            "date": filters["date_raw"] or str(today),
        },
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
    
