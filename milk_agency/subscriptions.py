from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone

from .models import (
    SubscriptionPlan,
    Subscription,
    SubscriptionItem,
    UserPayment,
    Customer
)


# -------------------------------------------------------
# SUBSCRIPTION DASHBOARD
# -------------------------------------------------------
@login_required
def subscription_dashboard(request):
    today = timezone.now().date()

    plans = SubscriptionPlan.objects.all()

    active_subscriptions = Subscription.objects.filter(
        active=True,
        end_date__gte=today
    ).select_related('customer', 'plan')

    expired_subscriptions = Subscription.objects.filter(
        end_date__lt=today
    ).select_related('customer', 'plan')

    expiring_soon = Subscription.objects.filter(
        active=True,
        end_date__range=[today, today + timezone.timedelta(days=5)]
    )

    total_active = active_subscriptions.count()
    total_expired = expired_subscriptions.count()

    context = {
        'plans': plans,
        'active_subscriptions': active_subscriptions,
        'expired_subscriptions': expired_subscriptions,
        'expiring_soon': expiring_soon,
        'total_active': total_active,
        'total_expired': total_expired,
    }

    return render(request, 'milk_agency/subscription/dashboard.html', context)


# -------------------------------------------------------
# CREATE SUBSCRIPTION PLAN
# -------------------------------------------------------
@login_required
def create_subscription_plan(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')
        description = request.POST.get('description')

        SubscriptionPlan.objects.create(
            name=name,
            price=price,
            description=description
        )
        messages.success(request, "Subscription plan created successfully")
        return redirect('milk_agency:subscription_dashboard')

    return render(request, 'milk_agency/subscription/create_plan.html')

@login_required
def edit_subscription_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)

    if request.method == 'POST':
        plan.name = request.POST.get('name')
        plan.price = request.POST.get('price')
        plan.description = request.POST.get('description')
        plan.save()
        messages.success(request, "Subscription plan updated successfully")
        return redirect('milk_agency:subscription_dashboard')

    return render(request, 'milk_agency/subscription/create_plan.html', {
        'plan': plan,
        'is_edit': True
    })
    
# -------------------------------------------------------
# ADD ITEMS TO PLAN
# -------------------------------------------------------
@login_required
def add_plan_item(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)

    if request.method == 'POST':
        item_id = request.POST.get('item')
        quantity = request.POST.get('quantity')

        SubscriptionItem.objects.create(
            subscription_plan=plan,
            item_id=item_id,
            quantity=quantity
        )
        messages.success(request, "Item added to plan")
        return redirect('milk_agency:subscription_dashboard')

    from .models import Item
    items = Item.objects.all()

    return render(request, 'milk_agency/subscription/add_plan_item.html', {
        'plan': plan,
        'items': items
    })


# -------------------------------------------------------
# ASSIGN SUBSCRIPTION TO CUSTOMER
# -------------------------------------------------------
@login_required
def assign_subscription(request):
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        plan_id = request.POST.get('plan')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        Subscription.objects.create(
            customer_id=customer_id,
            plan_id=plan_id,
            start_date=start_date,
            end_date=end_date,
            active=True
        )

        messages.success(request, "Subscription assigned successfully")
        return redirect('milk_agency:subscription_dashboard')

    customers = Customer.objects.filter(frozen=False)
    plans = SubscriptionPlan.objects.all()

    return render(request, 'milk_agency/subscription/assign_subscription.html', {
        'customers': customers,
        'plans': plans
    })


# -------------------------------------------------------
# TOGGLE SUBSCRIPTION ACTIVE / INACTIVE
# -------------------------------------------------------
@login_required
def toggle_subscription(request, subscription_id):
    subscription = get_object_or_404(Subscription, id=subscription_id)

    subscription.active = not subscription.active
    subscription.save()

    status = "activated" if subscription.active else "deactivated"
    messages.success(request, f"Subscription {status} for {subscription.customer.name}")

    return redirect('milk_agency:subscription_dashboard')


# -------------------------------------------------------
# CUSTOMER SUBSCRIPTION HISTORY
# -------------------------------------------------------
@login_required
def customer_subscription_history(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    subscriptions = Subscription.objects.filter(
        customer=customer
    ).select_related('plan').order_by('-start_date')

    payments = UserPayment.objects.filter(
        user=customer
    ).order_by('-created_at')

    return render(request, 'milk_agency/subscription/customer_history.html', {
        'customer': customer,
        'subscriptions': subscriptions,
        'payments': payments
    })


# -------------------------------------------------------
# RECORD PAYMENT FOR SUBSCRIPTION
# -------------------------------------------------------
@login_required
def record_subscription_payment(request, subscription_id):
    subscription = get_object_or_404(Subscription, id=subscription_id)

    if request.method == 'POST':
        amount = request.POST.get('amount')
        method = request.POST.get('method')

        UserPayment.objects.create(
            user=subscription.customer,
            amount=amount,
            subscription_plan=subscription.plan,
            method=method,
            status='SUCCESS',
            transaction_id=f"SUB-{timezone.now().timestamp()}"
        )

        messages.success(request, "Payment recorded successfully")
        return redirect('milk_agency:subscription_dashboard')

    return render(request, 'milk_agency/subscription/record_payment.html', {
        'subscription': subscription
    })