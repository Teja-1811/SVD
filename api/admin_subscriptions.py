from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone

from milk_agency.models import (
    SubscriptionPlan,
    CustomerSubscription,
    SubscriptionItem,
    UserPayment,
    Customer,
    Item
)

# -----------------------------------------
# 1️⃣ GET SUBSCRIPTION DASHBOARD DATA
# -----------------------------------------
@api_view(['GET'])
def api_subscription_dashboard(request):

    today = timezone.now().date()

    active = CustomerSubscription.objects.filter(
        is_active=True,
        end_date__gte=today
    ).select_related("customer", "subscription_plan")

    expired = CustomerSubscription.objects.filter(
        end_date__lt=today
    )

    expiring = CustomerSubscription.objects.filter(
        end_date__range=[today, today + timezone.timedelta(days=5)]
    )

    return Response({
        "active_subscriptions": active.count(),
        "expired_subscriptions": expired.count(),
        "expiring_soon": expiring.count(),
        "plans": SubscriptionPlan.objects.count()
    })


# -----------------------------------------
# 2️⃣ GET SUBSCRIPTION PLANS
# -----------------------------------------
@api_view(['GET'])
def api_get_plans(request):

    plans = SubscriptionPlan.objects.all()

    data = []

    for p in plans:
        data.append({
            "id": p.id,
            "name": p.name,
            "price": str(p.price),
            "duration_days": p.duration_in_days,
            "description": p.description
        })

    return Response(data)


# -----------------------------------------
# 3️⃣ CREATE PLAN
# -----------------------------------------
@api_view(['POST'])
def api_create_plan(request):

    plan = SubscriptionPlan.objects.create(
        name=request.data.get("name"),
        price=request.data.get("price"),
        duration_in_days=request.data.get("duration_days"),
        description=request.data.get("description")
    )

    return Response({
        "success": True,
        "plan_id": plan.id
    })


# -----------------------------------------
# 4️⃣ GET CUSTOMERS
# -----------------------------------------
@api_view(['GET'])
def api_subscription_customers(request):

    customers = Customer.objects.filter(
        frozen=False,
        user_type="user"
    )

    return Response([
        {
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
            "area": c.area
        }
        for c in customers
    ])


# -----------------------------------------
# 5️⃣ ASSIGN SUBSCRIPTION
# -----------------------------------------
@api_view(['POST'])
def api_assign_subscription(request):

    customer_id = request.data.get("customer")
    plan_id = request.data.get("plan")
    start_date = request.data.get("start_date")

    plan = get_object_or_404(SubscriptionPlan, id=plan_id)

    start = timezone.datetime.strptime(start_date, "%Y-%m-%d").date()
    end = start + timezone.timedelta(days=plan.duration_in_days)

    sub = CustomerSubscription.objects.create(
        customer_id=customer_id,
        subscription_plan_id=plan_id,
        start_date=start,
        end_date=end,
        is_active=True
    )

    return Response({
        "success": True,
        "subscription_id": sub.id
    })


# -----------------------------------------
# 6️⃣ GET CUSTOMER SUBSCRIPTIONS
# -----------------------------------------
@api_view(['GET'])
def api_customer_subscriptions(request):

    customer_id = request.GET.get("customer")

    subs = CustomerSubscription.objects.select_related(
        "customer",
        "subscription_plan"
    )

    if customer_id:
        subs = subs.filter(customer_id=customer_id)

    data = []

    for s in subs:
        data.append({
            "id": s.id,
            "customer": s.customer.name,
            "plan": s.subscription_plan.name,
            "start_date": str(s.start_date),
            "end_date": str(s.end_date),
            "is_active": s.is_active
        })

    return Response(data)


# -----------------------------------------
# 7️⃣ TOGGLE SUBSCRIPTION
# -----------------------------------------
@api_view(['POST'])
def api_toggle_subscription(request, subscription_id):

    sub = get_object_or_404(CustomerSubscription, id=subscription_id)

    sub.is_active = not sub.is_active
    sub.save()

    return Response({
        "success": True,
        "is_active": sub.is_active
    })


# -----------------------------------------
# 8️⃣ RECORD PAYMENT
# -----------------------------------------
@api_view(['POST'])
def api_record_subscription_payment(request, subscription_id):

    sub = get_object_or_404(CustomerSubscription, id=subscription_id)

    payment = UserPayment.objects.create(
        subscription=sub,
        user=sub.customer,
        amount=request.data.get("amount"),
        transaction_id=request.data.get("transaction_id"),
        method=request.data.get("method"),
        status="SUCCESS"
    )

    return Response({
        "success": True,
        "payment_id": payment.id
    })


# -----------------------------------------
# 9️⃣ TODAY DELIVERIES
# -----------------------------------------
@api_view(['GET'])
def api_today_deliveries(request):

    today = timezone.now().date()

    deliveries = CustomerSubscription.objects.filter(
        is_active=True,
        end_date__gte=today
    ).select_related("customer", "subscription_plan")

    data = []

    for d in deliveries:
        data.append({
            "customer": d.customer.name,
            "phone": d.customer.phone,
            "plan": d.subscription_plan.name,
            "start_date": str(d.start_date),
            "end_date": str(d.end_date)
        })

    return Response(data)