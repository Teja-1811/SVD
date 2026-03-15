from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import (
    SubscriptionPlan,
    CustomerSubscription,
    SubscriptionItem,
    UserPayment,
    Customer,
    Item
)


def recalculate_plan_price(plan):
    """
    Recompute the total subscription plan price from its items.
    Formula: sum(item.price * quantity) for the plan * duration_in_days.
    """
    total_daily = Decimal("0")
    for plan_item in plan.items.all():
        item_price = plan_item.price or Decimal("0")
        quantity = plan_item.quantity or 0
        total_daily += item_price * Decimal(quantity)

    duration = plan.duration_in_days or 0
    plan.price = total_daily * Decimal(duration)
    plan.save(update_fields=["price"])


# -------------------------------------------------------
# SUBSCRIPTION DASHBOARD
# -------------------------------------------------------
@login_required
def subscription_dashboard(request):

    today = timezone.now().date()

    # Auto deactivate expired subscriptions
    CustomerSubscription.objects.filter(
        end_date__lt=today,
        is_active=True
    ).update(is_active=False)

    plans = SubscriptionPlan.objects.all()

    active_subscriptions = CustomerSubscription.objects.filter(
        is_active=True,
        end_date__gte=today
    ).select_related("customer", "subscription_plan")
    
    de_activated_subscriptions = CustomerSubscription.objects.filter(
        is_active=False,
        end_date__gte=today
    ).select_related("customer", "subscription_plan")   

    expired_subscriptions = CustomerSubscription.objects.filter(
        end_date__lt=today
    ).select_related("customer", "subscription_plan")

    expiring_soon = CustomerSubscription.objects.filter(
        is_active=True,
        end_date__range=[today, today + timezone.timedelta(days=5)]
    ).select_related("customer", "subscription_plan")

    items = Item.objects.all()
    customers = Customer.objects.filter(frozen=False, user_type="user")

    context = {
        "plans": plans,
        "active_subscriptions": active_subscriptions,
        "de_activated_subscriptions": de_activated_subscriptions,
        "expired_subscriptions": expired_subscriptions,
        "expiring_soon": expiring_soon,
        "items": items,
        "customers": customers,
        "total_active": active_subscriptions.count(),
        "total_expired": expired_subscriptions.count(),
        "total_plans": plans.count(),
        "expiring_count": expiring_soon.count(),
    }

    return render(
        request,
        "milk_agency/subscription/dashboard.html",
        context
    )


# -------------------------------------------------------
# CREATE SUBSCRIPTION PLAN
# -------------------------------------------------------
@login_required
def create_subscription_plan(request):

    if request.method == "POST":

        name = request.POST.get("name")
        days = request.POST.get("duration_in_days")
        description = request.POST.get("description")

        SubscriptionPlan.objects.create(
            name=name,
            price=0,
            duration_in_days=days,
            description=description
        )

        messages.success(request, "Subscription plan created successfully")

    return redirect("milk_agency:subscription_dashboard")


# -------------------------------------------------------
# EDIT SUBSCRIPTION PLAN
# -------------------------------------------------------
@login_required
def edit_subscription_plan(request, plan_id):

    plan = get_object_or_404(SubscriptionPlan, id=plan_id)

    if request.method == "POST":

        plan.name = request.POST.get("name")
        plan.duration_in_days = request.POST.get("duration_in_days")
        plan.description = request.POST.get("description")

        plan.save()
        recalculate_plan_price(plan)

        messages.success(request, "Subscription plan updated successfully")

    return redirect("milk_agency:subscription_dashboard")


# -------------------------------------------------------
# ADD ITEM TO PLAN
# -------------------------------------------------------
@login_required
def add_plan_item(request, plan_id):

    plan = get_object_or_404(SubscriptionPlan, id=plan_id)

    if request.method == "POST":

        item_id = request.POST.get("item")
        quantity = request.POST.get("quantity")
        price = request.POST.get("price") or 0

        SubscriptionItem.objects.update_or_create(
            subscription_plan=plan,
            item_id=item_id,
            defaults={
                "quantity": quantity,
                "price": price,
            }
        )

        recalculate_plan_price(plan)
        messages.success(request, "Item added to plan")

    return redirect("milk_agency:subscription_dashboard")


# -------------------------------------------------------
# UPDATE PLAN ITEM
# -------------------------------------------------------
@login_required
def update_plan_item(request, item_id):

    plan_item = get_object_or_404(SubscriptionItem, id=item_id)

    if request.method == "POST":

        quantity = request.POST.get("quantity")
        price = request.POST.get("price")

        if quantity is not None and quantity != "":
            plan_item.quantity = quantity

        if price is not None and price != "":
            plan_item.price = price

        plan_item.save()
        recalculate_plan_price(plan_item.subscription_plan)

        messages.success(request, "Item quantity updated")

    return redirect("milk_agency:subscription_dashboard")


# -------------------------------------------------------
# DELETE PLAN ITEM
# -------------------------------------------------------
@login_required
def delete_plan_item(request, item_id):

    plan_item = get_object_or_404(SubscriptionItem, id=item_id)
    plan = plan_item.subscription_plan

    plan_item.delete()
    recalculate_plan_price(plan)

    messages.success(request, "Item removed from plan")

    return redirect("milk_agency:subscription_dashboard")


# -------------------------------------------------------
# ASSIGN SUBSCRIPTION
# -------------------------------------------------------
@login_required
def assign_subscription(request):

    if request.method == "POST":

        customer_id = request.POST.get("customer")
        plan_id = request.POST.get("plan")
        start_date = request.POST.get("start_date")

        plan = SubscriptionPlan.objects.get(id=plan_id)

        # Default duration example (30 days)
        end_date = timezone.datetime.strptime(start_date, "%Y-%m-%d").date() + timezone.timedelta(days=30)

        CustomerSubscription.objects.create(
            customer_id=customer_id,
            subscription_plan_id=plan_id,
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )

        messages.success(request, "Subscription assigned successfully")

    return redirect("milk_agency:subscription_dashboard")


# -------------------------------------------------------
# TOGGLE SUBSCRIPTION
# -------------------------------------------------------
@login_required
def toggle_subscription(request, subscription_id):

    subscription = get_object_or_404(CustomerSubscription, id=subscription_id)

    subscription.is_active = not subscription.is_active
    subscription.save()

    status = "activated" if subscription.is_active else "deactivated"

    messages.success(
        request,
        f"Subscription {status} for {subscription.customer.name}"
    )

    return redirect("milk_agency:subscription_dashboard")


# -------------------------------------------------------
# RECORD SUBSCRIPTION PAYMENT
# -------------------------------------------------------
@login_required
def record_subscription_payment(request, subscription_id):

    subscription = get_object_or_404(CustomerSubscription, id=subscription_id)

    if request.method == "POST":

        amount = request.POST.get("amount")
        method = request.POST.get("method")
        transaction_id = request.POST.get("transaction_id")

        UserPayment.objects.create(
            subscription=subscription,
            user=subscription.customer,
            amount=amount,
            transaction_id=transaction_id,
            method=method,
            status="SUCCESS"
        )

        messages.success(request, "Payment recorded successfully")

        return redirect("milk_agency:subscription_dashboard")

    return render(
        request,
        "milk_agency/subscription/record_payment.html",
        {"subscription": subscription}
    )


# -------------------------------------------------------
# CUSTOMER SUBSCRIPTION HISTORY
# -------------------------------------------------------
@login_required
def customer_subscription_history(request):

    customer_id = request.GET.get("customer")
    plan_id = request.GET.get("plan")

    subscriptions = CustomerSubscription.objects.select_related(
        "customer", "subscription_plan"
    )

    payments = UserPayment.objects.select_related("user")

    if customer_id:
        subscriptions = subscriptions.filter(customer_id=customer_id)
        payments = payments.filter(user_id=customer_id)

    if plan_id:
        subscriptions = subscriptions.filter(subscription_plan_id=plan_id)

    customers = Customer.objects.all()
    plans = SubscriptionPlan.objects.all()

    context = {
        "subscriptions": subscriptions,
        "payments": payments,
        "customers": customers,
        "plans": plans,
    }

    return render(
        request,
        "milk_agency/subscription/customer_history.html",
        context
    )
# -------------------------------------------------------
# TODAY DELIVERIES
# -------------------------------------------------------
@login_required
def today_deliveries(request):

    today = timezone.now().date()

    subscriptions = CustomerSubscription.objects.filter(
        is_active=True,
        end_date__gte=today
    ).select_related(
        "customer", "subscription_plan"
    ).prefetch_related(
        "subscription_plan__items__item",
        "subscriptionorder_set"
    )

    deliveries = []
    for sub in subscriptions:
        todays_orders = [o for o in sub.subscriptionorder_set.all() if o.date == today]
        status = "Pending"
        if todays_orders and all(order.delivered for order in todays_orders):
            status = "Delivered"

        deliveries.append(
            {
                "customer": sub.customer,
                "plan": sub.subscription_plan,
                "items": [
                    {
                        "name": plan_item.item.name,
                        "quantity": plan_item.quantity,
                    }
                    for plan_item in sub.subscription_plan.items.all()
                ],
                "status": status,
            }
        )

    return render(
        request,
        "milk_agency/subscription/today_deliveries.html",
        {"deliveries": deliveries}
    )
