from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone

from .user_offers import get_active_user_offers
from milk_agency.models import (
    AutoUPISetting,
    Customer,
    CustomerSubscription,
    SubscriptionItem,
    SubscriptionPause,
    SubscriptionPlan,
)


def _serialize_customer(customer):
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


# =======================================================
def _get_customer_or_response(user_id):
    if not user_id:
        return None, Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        return Customer.objects.get(id=int(user_id)), None
    except (Customer.DoesNotExist, ValueError):
        return None, Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    val = str(value).strip().lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return None


# =======================================================
# CUSTOMER DASHBOARD API
# =======================================================
@api_view(["GET"])
def user_dashboard_api(request):
    user_id = request.GET.get("user_id")

    customer, error = _get_customer_or_response(user_id)
    if error:
        return error

    latest_subscription = CustomerSubscription.objects.filter(customer=customer).order_by('-start_date').first()

    if latest_subscription:
        plan = latest_subscription.subscription_plan
        plan_items = SubscriptionItem.objects.filter(subscription_plan=plan).select_related("item")
        formatted_items = [
            {
                "item_id": item.item.id,
                "item_name": item.item.name,
                "quantity": item.quantity,
                "price": float(item.price),
                "per": item.per,
            }
            for item in plan_items
        ]
        subscription_payload = {
            "id": latest_subscription.id,
            "plan_id": plan.id,
            "plan": plan.name,
            "price": float(plan.price),
            "description": plan.description,
            "duration_in_days": plan.duration_in_days,
            "start_date": latest_subscription.start_date,
            "end_date": latest_subscription.end_date,
            "is_active": latest_subscription.is_active,
            "items": formatted_items,
        }
    else:
        subscription_payload = {
            "plan": "No active subscription",
            "price": 0,
            "description": "",
            "duration_in_days": 0,
            "start_date": None,
            "end_date": None,
            "is_active": False,
            "items": [],
        }

    history_qs = CustomerSubscription.objects.filter(customer=customer).order_by('-start_date')
    history = [
        {
            "plan": sub.subscription_plan.name,
            "start_date": sub.start_date,
            "end_date": sub.end_date,
            "status": "Active" if sub.is_active else "Inactive",
        }
        for sub in history_qs
    ]

    pause_qs = SubscriptionPause.objects.filter(
        subscription__customer=customer
    ).select_related("subscription__subscription_plan").order_by('-pause_date')
    pauses = [
        {
            "plan": pause.subscription.subscription_plan.name,
            "pause_date": pause.pause_date,
            "resume_date": pause.resume_date,
            "reason": pause.reason,
            "status": "Paused" if not pause.is_resumed else "Resumed",
        }
        for pause in pause_qs
    ]

    profile = _serialize_customer(customer)

    auto_setting = getattr(customer, "auto_upi_setting", None)

    auto_upi_payload = {
        "is_active": auto_setting.is_active if auto_setting else False,
        "upi_id": auto_setting.upi_id if auto_setting else "",
        "max_amount": float(auto_setting.max_amount) if auto_setting else 0,
        "last_payment_amount": float(auto_setting.last_payment_amount) if auto_setting else 0,
        "last_payment_date": auto_setting.last_payment_date if auto_setting else None,
    }

    response_payload = {
        "status": True,
        "customer": profile,
        "subscription": subscription_payload,
        "subscription_history": history,
        "subscription_pauses": pauses,
        "offers": get_active_user_offers(),
        "auto_upi": auto_upi_payload,
    }

    return Response(response_payload, status=200)


@api_view(["POST"])
def user_profile_update(request):
    user_id = request.data.get("user_id")
    customer, error = _get_customer_or_response(user_id)
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
        if field in ("is_commissioned", "is_delivery"):
            bool_value = _coerce_bool(value)
            if bool_value is None:
                continue
            updates[field] = bool_value
        else:
            updates[field] = value

    if "phone" in updates and updates["phone"] != customer.phone:
        if Customer.objects.filter(phone=updates["phone"]).exclude(pk=customer.pk).exists():
            return Response({"error": "Phone already in use"}, status=status.HTTP_400_BAD_REQUEST)

    if not updates:
        return Response({"error": "no profile updates provided"}, status=status.HTTP_400_BAD_REQUEST)

    for field, value in updates.items():
        setattr(customer, field, value)
    customer.save(update_fields=list(updates.keys()))

    return Response(
        {"status": "success", "customer": _serialize_customer(customer)},
        status=200,
    )

@api_view(["GET"])
def plans_available_api(request):
    plans = SubscriptionPlan.objects.filter(is_active=True)

    items = SubscriptionItem.objects.filter(
        subscription_plan__in=plans
    ).select_related("item", "subscription_plan")

    items_by_plan = {}

    for item in items:
        items_by_plan.setdefault(item.subscription_plan_id, []).append({
            "item_id": item.item.id,
            "item_name": item.item.name,
            "quantity": item.quantity,
            "price": float(item.price),
            "per": item.per,
        })

    data = []

    for plan in plans:
        data.append({
            "id": plan.id,
            "name": plan.name,
            "price": float(plan.price),
            "description": plan.description,
            "items": items_by_plan.get(plan.id, [])
        })

    return Response({"plans": data}, status=200)


@api_view(["GET"])
def subscribed_plan_api(request):
    customer_id = request.GET.get("customer_id")
    plan = None
    try:
        plan = CustomerSubscription.objects.filter(customer=customer_id).latest('start_date')
        plan_name = plan.subscription_plan.name
    except CustomerSubscription.DoesNotExist:
        plan_name = "No active subscription"
        
    try:
        if plan:
            items = SubscriptionItem.objects.filter(subscription_plan=plan.subscription_plan)
            item_list = []
            for item in items:
                item_list.append({
                    "item_id": item.item.id,
                    "item_name": item.item.name,
                    "quantity": item.quantity,
                    "price": float(item.price),
                    "per": item.per,
                })
        else:
            item_list = []
    except SubscriptionItem.DoesNotExist:
        item_list = []
        
        
    #plan details
    data = {
        "plan": plan_name,
        "price" : float(plan.subscription_plan.price) if plan else 0,
        "description" : plan.subscription_plan.description if plan else "",
        # items in the subscription
        "items": item_list 
    }
    
    return Response(data, status=200)
    
@api_view(["GET"])
def subscription_history_api(request):
    customer_id = request.GET.get("customer_id")
    try:
        subscriptions = CustomerSubscription.objects.filter(customer=customer_id).order_by('-start_date')
        subscription_list = []
        for sub in subscriptions:
            subscription_list.append({
                "plan": sub.subscription_plan.name,
                "start_date": sub.start_date,
                "end_date": sub.end_date,
                "status": "Active" if sub.is_active else "Inactive",
            })
    except CustomerSubscription.DoesNotExist:
        subscription_list = []
    
    return Response({"subscriptions": subscription_list}, status=200)

@api_view(["GET"])
def subscription_pauses_api(request):
    customer_id = request.GET.get("customer_id")
    try:
        pauses = SubscriptionPause.objects.filter(subscription__customer=customer_id).order_by('-pause_date')
        pause_list = []
        for pause in pauses:
            pause_list.append({
                "plan": pause.subscription.subscription_plan.name,
                "pause_date": timezone.localtime(pause.pause_date),
                "status": "Paused" if not pause.is_resumed else "Resumed",
            })
    except SubscriptionPause.DoesNotExist:
        pause_list = []
    
    return Response({"pauses": pause_list}, status=200)

