from rest_framework.decorators import api_view
from rest_framework.response import Response

from .user_offers import get_active_user_offers
from milk_agency.models import Customer, CustomerSubscription, SubscriptionItem, SubscriptionPause, SubscriptionPlan


# =======================================================
# CUSTOMER DASHBOARD API
# =======================================================
@api_view(["GET"])
def user_dashboard_api(request):
    user_id = request.GET.get("user_id")

    if not user_id:
        return Response({"error": "user_id is required"}, status=400)

    try:
        customer = Customer.objects.get(id=int(user_id))
    except (Customer.DoesNotExist, ValueError):
        return Response({"error": "Customer not found"}, status=404)

    latest_subscription = CustomerSubscription.objects.filter(customer=customer).order_by('-start_date').first()

    if latest_subscription:
        plan = latest_subscription.subscription_plan
        plan_items = SubscriptionItem.objects.filter(subscription_plan=plan).select_related("item")
        formatted_items = [
            {
                "item_id": item.item.id,
                "item_name": item.item.name,
                "quantity": item.quantity,
            }
            for item in plan_items
        ]
        subscription_payload = {
            "id": latest_subscription.id,
            "plan_id": plan.id,
            "plan": plan.name,
            "price": plan.price,
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

    pause_qs = SubscriptionPause.objects.filter(subscription__customer=customer).select_related("subscription__subscription_plan").order_by('-date')
    pauses = [
        {
            "plan": pause.subscription.subscription_plan.name,
            "pause_date": pause.date,
            "reason": pause.reason,
            "status": "Paused",
        }
        for pause in pause_qs
    ]

    profile = {
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
        "due": float(customer.get_actual_due() or 0),
    }

    response_payload = {
        "status": True,
        "customer": profile,
        "subscription": subscription_payload,
        "subscription_history": history,
        "subscription_pauses": pauses,
        "offers": get_active_user_offers(),
    }

    return Response(response_payload, status=200)

@api_view(["GET"])
def plans_available_api(request):
    plans = SubscriptionPlan.objects.filter(is_active=True)
    data = []
    for plan in plans:
        data.append({
            "id": plan.id,
            "name": plan.name,
            "price": plan.price,
            "description": plan.description,
        })
    return Response({"plans": data}, status=200)


@api_view(["GET"])
def subscribed_plan_api(request):
    customer_id = request.GET.get("customer_id")
    try:
        plan = CustomerSubscription.objects.filter(customer=customer_id).latest('start_date')
        plan_name = plan.subscription_plan.name
    except CustomerSubscription.DoesNotExist:
        plan_name = "No active subscription"
        
    try:
        items = SubscriptionItem.objects.filter(subscription_plan=plan.subscription_plan)
        item_list = []
        for item in items:
            item_list.append({
                "item_id": item.item.id,
                "item_name": item.item.name,
                "quantity": item.quantity,
            })
    except SubscriptionItem.DoesNotExist:
        item_list = []
        
        
    #plan details
    data = {
        "plan": plan_name,
        "price" : plan.subscription_plan.price,
        "description" : plan.subscription_plan.description,
        # items in the subscription
        "items": item_list
        
    }
    
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
                "pause_date": pause.pause_date,
                "resume_date": pause.resume_date,
                "status": "Paused" if not pause.is_resumed else "Resumed",
            })
    except SubscriptionPause.DoesNotExist:
        pause_list = []
    
    return Response({"pauses": pause_list}, status=200)

