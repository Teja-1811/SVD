from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.user_bill_pdf_utils import UserPDFGenerator
from customer_portal.models import CustomerOrder, CustomerOrderItem
from milk_agency.models import Bill, BillItem, Customer, SubscriptionItem, SubscriptionPlan
from milk_agency.order_pricing import DELIVERY_ITEM_CODE

from .user_api_helpers import (
    coerce_bool,
    find_linked_order_for_bill,
    get_customer_or_response,
    get_delivery_charge_for_bill,
    get_latest_subscription,
    serialize_auto_upi,
    serialize_customer,
    serialize_customer_subscription,
    serialize_subscription_history,
    serialize_subscription_item,
    serialize_subscription_pauses,
)
from .user_offers import get_active_user_offers


def _serialize_bill_list_item(bill, current_due):
    return {
        "id": bill.id,
        "invoice_number": bill.invoice_number,
        "invoice_date": bill.invoice_date,
        "total_amount": float(bill.total_amount),
        "opening_due": float(bill.op_due_amount),
        "profit": float(bill.profit),
        "current_due": current_due,
    }


def _serialize_bill_item(bill_item):
    return {
        "item_id": bill_item.item.id,
        "code": bill_item.item.code,
        "name": bill_item.item.name,
        "mrp": float(bill_item.item.mrp),
        "price_per_unit": float(bill_item.price_per_unit),
        "discount": float(bill_item.discount),
        "quantity": bill_item.quantity,
        "total_amount": float(bill_item.total_amount),
    }


def _serialize_order_item(order_item):
    return {
        "item_id": order_item.item.id,
        "code": order_item.item.code,
        "name": order_item.item.name,
        "requested_quantity": order_item.requested_quantity,
        "requested_price": float(order_item.requested_price),
        "approved_quantity": order_item.approved_quantity,
        "approved_price": float(order_item.approved_price),
        "discount": float(order_item.discount),
        "discount_total": float(order_item.discount_total),
        "requested_total": float(order_item.requested_total),
        "approved_total": float(order_item.approved_total),
    }


def _serialize_order(order):
    total_amount = float(order.total_amount)
    delivery_charge = float(order.delivery_charge)
    return {
        "id": order.id,
        "order_number": order.order_number,
        "order_date": order.order_date,
        "delivery_date": order.delivery_date,
        "status": order.status,
        "delivery_address": order.delivery_address,
        "total_amount": total_amount,
        "delivery_charge": delivery_charge,
        "grand_total": total_amount + delivery_charge,
        "approved_total_amount": float(order.approved_total_amount),
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


@api_view(["GET"])
def user_dashboard_api(request):
    customer, error = get_customer_or_response(request.GET.get("user_id"))
    if error:
        return error

    latest_subscription = get_latest_subscription(customer)
    plan_items = []
    if latest_subscription:
        plan_items = SubscriptionItem.objects.filter(
            subscription_plan=latest_subscription.subscription_plan
        ).select_related("item")

    response_payload = {
        "status": True,
        "customer": serialize_customer(customer),
        "subscription": serialize_customer_subscription(latest_subscription, items=plan_items),
        "subscription_history": serialize_subscription_history(customer),
        "subscription_pauses": serialize_subscription_pauses(customer),
        "offers": get_active_user_offers(),
        "auto_upi": serialize_auto_upi(customer),
    }
    return Response(response_payload, status=200)


@api_view(["GET"])
def user_bills_api(request):
    customer, error = get_customer_or_response(request.GET.get("user_id"))
    if error:
        return error

    current_due = float(customer.get_actual_due() or 0)
    bills = Bill.objects.filter(customer=customer, is_deleted=False).order_by("-invoice_date", "-id")
    data = [_serialize_bill_list_item(bill, current_due) for bill in bills]
    return Response({"bills": data}, status=200)


@api_view(["GET"])
def user_bill_detail_api(request, bill_id):
    customer, error = get_customer_or_response(request.GET.get("user_id"))
    if error:
        return error

    bill = (
        Bill.objects.filter(customer=customer, id=bill_id, is_deleted=False)
        .select_related("customer")
        .first()
    )
    if not bill:
        return Response({"error": "Bill not found"}, status=404)

    bill_items = list(BillItem.objects.filter(bill=bill).select_related("item"))
    linked_order = find_linked_order_for_bill(customer, bill)
    delivery_charge = float(
        get_delivery_charge_for_bill(bill, bill_items=bill_items, linked_order=linked_order)
    )
    item_payload = [
        _serialize_bill_item(bill_item)
        for bill_item in bill_items
        if getattr(bill_item.item, "code", "") != DELIVERY_ITEM_CODE
    ]

    bill_payload = {
        "id": bill.id,
        "invoice_number": bill.invoice_number,
        "invoice_date": bill.invoice_date,
        "total_amount": float(bill.total_amount),
        "items_subtotal": float(bill.total_amount) - delivery_charge,
        "delivery_charge": delivery_charge,
        "opening_due": float(bill.op_due_amount),
        "last_paid": float(bill.last_paid),
        "profit": float(bill.profit),
        "current_due": float(customer.get_actual_due() or 0),
    }
    return Response({"bill": bill_payload, "items": item_payload}, status=200)


@api_view(["GET"])
def user_bill_download_api(request, bill_id):
    customer, error = get_customer_or_response(request.GET.get("user_id"))
    if error:
        return error

    bill = Bill.objects.filter(customer=customer, id=bill_id, is_deleted=False).first()
    if not bill:
        return Response({"error": "Bill not found"}, status=404)

    return UserPDFGenerator().generate_and_return_pdf(bill, request)


@api_view(["GET"])
def user_order_detail_api(request, order_id):
    customer, error = get_customer_or_response(request.GET.get("user_id"))
    if error:
        return error

    order = (
        CustomerOrder.objects.filter(customer=customer, id=order_id)
        .select_related("customer")
        .first()
    )
    if not order:
        return Response({"error": "Order not found"}, status=404)

    items = CustomerOrderItem.objects.filter(order=order).select_related("item")
    return Response(
        {
            "order": _serialize_order(order),
            "items": [_serialize_order_item(item) for item in items],
        },
        status=200,
    )


@api_view(["POST"])
def user_profile_update(request):
    customer, error = get_customer_or_response(request.data.get("user_id"))
    if error:
        return error

    allowed_fields = [
        "name",
        "phone",
        "shop_name",
        "flat_number",
        "area",
        "city",
        "state",
        "pin_code",
        "is_delivery",
    ]
    updates = {}
    for field in allowed_fields:
        value = request.data.get(field)
        if value is None:
            continue

        if field == "is_delivery":
            bool_value = coerce_bool(value)
            if bool_value is None:
                continue
            updates[field] = bool_value
            continue

        updates[field] = value

    if "phone" in updates and updates["phone"] != customer.phone:
        if Customer.objects.filter(phone=updates["phone"]).exclude(pk=customer.pk).exists():
            return Response({"error": "Phone already in use"}, status=status.HTTP_400_BAD_REQUEST)

    if not updates:
        return Response({"error": "no profile updates provided"}, status=status.HTTP_400_BAD_REQUEST)

    for field, value in updates.items():
        setattr(customer, field, value)
    customer.save(update_fields=list(updates.keys()))

    return Response({"status": "success", "customer": serialize_customer(customer)}, status=200)


@api_view(["GET"])
def plans_available_api(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("id")
    items = SubscriptionItem.objects.filter(subscription_plan__in=plans).select_related("item", "subscription_plan")

    items_by_plan = {}
    for item in items:
        items_by_plan.setdefault(item.subscription_plan_id, []).append(item)

    data = [
        {
            "id": plan.id,
            "name": plan.name,
            "price": float(plan.price),
            "description": plan.description,
            "duration_in_days": plan.duration_in_days,
            "items": [serialize_subscription_item(item) for item in items_by_plan.get(plan.id, [])],
        }
        for plan in plans
    ]
    return Response({"plans": data}, status=200)


@api_view(["GET"])
def current_subscription_api(request):
    customer, error = get_customer_or_response(
        request.GET.get("user_id") or request.GET.get("customer_id")
    )
    if error:
        return error

    subscription = get_latest_subscription(customer, active_only=True)
    if subscription:
        items = SubscriptionItem.objects.filter(subscription_plan=subscription.subscription_plan).select_related("item")
    else:
        items = []

    return Response(serialize_customer_subscription(subscription, items=items), status=200)


@api_view(["GET"])
def subscription_history_api(request):
    customer, error = get_customer_or_response(
        request.GET.get("user_id") or request.GET.get("customer_id")
    )
    if error:
        return error

    return Response({"subscriptions": serialize_subscription_history(customer)}, status=200)
