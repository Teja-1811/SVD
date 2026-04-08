from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from customer_portal.models import CustomerOrder
from milk_agency.models import (
    BillItem,
    Customer,
    CustomerSubscription,
    Offers,
    SubscriptionItem,
    SubscriptionPause,
)
from milk_agency.order_pricing import DELIVERY_ITEM_CODE


def get_customer_or_response(user_id, *, allow_frozen=True):
    try:
        if not user_id:
            raise TypeError

        filters = {"id": int(user_id)}
        if not allow_frozen:
            filters["frozen"] = False

        return Customer.objects.get(**filters), None
    except TypeError:
        return None, Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    except (Customer.DoesNotExist, ValueError):
        return None, Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)


def coerce_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None

    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def serialize_customer(customer):
    due_amount = customer.get_actual_due() or 0
    return {
        "id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "shop_name": customer.shop_name,
        "retailer_id": customer.retailer_id,
        "flat_number": customer.flat_number,
        "area": customer.area,
        "city": customer.city,
        "state": customer.state,
        "pin_code": customer.pin_code,
        "account_status": "Active" if customer.is_active else "Inactive",
        "is_commissioned": customer.is_commissioned,
        "is_delivery": customer.is_delivery,
        "frozen": customer.frozen,
        "user_type": customer.user_type,
        "due": float(due_amount),
    }


def serialize_subscription_item(item):
    return {
        "item_id": item.item.id,
        "item_name": item.item.name,
        "quantity": item.quantity,
        "price": float(item.price),
        "per": item.per,
    }


def serialize_subscription_plan(plan, items=None):
    plan_items = items
    if plan_items is None:
        plan_items = SubscriptionItem.objects.filter(subscription_plan=plan).select_related("item")

    return {
        "id": plan.id,
        "name": plan.name,
        "price": float(plan.price),
        "description": plan.description,
        "duration_in_days": plan.duration_in_days,
        "items": [serialize_subscription_item(item) for item in plan_items],
    }


def serialize_customer_subscription(subscription, items=None):
    if not subscription:
        return {
            "plan": "No active subscription",
            "price": 0,
            "description": "",
            "duration_in_days": 0,
            "start_date": None,
            "end_date": None,
            "is_active": False,
            "items": [],
        }

    payload = serialize_subscription_plan(subscription.subscription_plan, items=items)
    payload.update(
        {
            "id": subscription.id,
            "subscription_id": subscription.id,
            "plan_id": subscription.subscription_plan_id,
            "plan": subscription.subscription_plan.name,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "is_active": subscription.is_active,
        }
    )
    return payload


def get_latest_subscription(customer, *, active_only=False):
    filters = {"customer": customer}
    if active_only:
        filters["is_active"] = True
    return (
        CustomerSubscription.objects.filter(**filters)
        .select_related("subscription_plan")
        .order_by("-start_date", "-id")
        .first()
    )


def serialize_subscription_history(customer):
    subscriptions = (
        CustomerSubscription.objects.filter(customer=customer)
        .select_related("subscription_plan")
        .order_by("-start_date", "-id")
    )
    return [
        {
            "plan": subscription.subscription_plan.name,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "status": "Active" if subscription.is_active else "Inactive",
        }
        for subscription in subscriptions
    ]


def serialize_subscription_pauses(customer):
    pauses = (
        SubscriptionPause.objects.filter(subscription__customer=customer)
        .select_related("subscription__subscription_plan")
        .order_by("-pause_date", "-id")
    )
    return [
        {
            "plan": pause.subscription.subscription_plan.name,
            "pause_date": pause.pause_date,
            "resume_date": pause.resume_date,
            "reason": pause.reason,
            "status": "Paused" if not pause.is_resumed else "Resumed",
        }
        for pause in pauses
    ]


def serialize_auto_upi(customer):
    auto_setting = getattr(customer, "auto_upi_setting", None)
    if not auto_setting:
        return {
            "is_active": False,
            "upi_id": "",
            "max_amount": 0,
            "last_payment_amount": 0,
            "last_payment_date": None,
        }

    return {
        "is_active": auto_setting.is_active,
        "upi_id": auto_setting.upi_id,
        "max_amount": float(auto_setting.max_amount),
        "last_payment_amount": float(auto_setting.last_payment_amount),
        "last_payment_date": auto_setting.last_payment_date,
    }


def get_active_offers(*, offer_for="user"):
    today = timezone.localdate()
    offers = (
        Offers.objects.filter(
            offer_for=offer_for,
            is_active=True,
            start_date__lte=today,
            end_date__gte=today,
        )
        .prefetch_related("offeritems_set__item")
        .order_by("-start_date", "-id")
    )

    return [
        {
            "id": offer.id,
            "name": offer.name,
            "offer_type": offer.offer_type,
            "price": float(offer.price),
            "description": offer.description,
            "start_date": offer.start_date,
            "end_date": offer.end_date,
            "items": [
                {
                    "item_id": offer_item.item.id,
                    "item_name": offer_item.item.name,
                    "buy_qty": offer_item.buy_qty,
                    "offer_qty": offer_item.offer_qty,
                    "offer_price": float(offer_item.offer_price),
                }
                for offer_item in offer.offeritems_set.select_related("item").all()
            ],
        }
        for offer in offers
    ]


def find_linked_order_for_bill(customer, bill):
    if not customer:
        return None

    direct_match = getattr(bill, "linked_orders", None)
    if direct_match is not None:
        linked_order = direct_match.order_by("-id").first()
        if linked_order:
            return linked_order

    exact_match = (
        CustomerOrder.objects.filter(
            customer=customer,
            order_date=bill.invoice_date,
            approved_total_amount=bill.total_amount,
        )
        .order_by("-id")
        .first()
    )
    if exact_match:
        return exact_match

    dated_orders = CustomerOrder.objects.filter(
        customer=customer,
        order_date=bill.invoice_date,
    ).order_by("-id")
    for order in dated_orders:
        approved_total = Decimal(order.approved_total_amount or 0)
        delivery_charge = Decimal(order.delivery_charge or 0)
        bill_total = Decimal(bill.total_amount or 0)
        if approved_total + delivery_charge == bill_total:
            return order

    return dated_orders.first() or CustomerOrder.objects.filter(customer=customer).order_by("-order_date", "-id").first()


def get_delivery_charge_for_bill(bill, *, bill_items=None, linked_order=None):
    items = bill_items
    if items is None:
        items = list(BillItem.objects.filter(bill=bill).select_related("item"))

    for bill_item in items:
        if getattr(bill_item.item, "code", "") == DELIVERY_ITEM_CODE:
            return Decimal(bill_item.total_amount or 0)

    order = linked_order or find_linked_order_for_bill(bill.customer, bill)
    if order:
        return Decimal(order.delivery_charge or 0)

    return Decimal("0")
