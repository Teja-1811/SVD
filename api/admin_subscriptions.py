from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from milk_agency.models import (
    Customer,
    CustomerSubscription,
    Item,
    SubscriptionItem,
    SubscriptionPlan,
    UserPayment,
)


def _parse_date_yyyy_mm_dd(value):
    if not value:
        return None
    try:
        return timezone.datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _serialize_plan(plan):
    return {
        "id": plan.id,
        "name": plan.name,
        "price": str(plan.price),
        "duration_in_days": plan.duration_in_days,
        "description": plan.description,
        "items": [
            {
                "id": i.id,
                "item_id": i.item_id,
                "item_name": i.item.name if i.item else None,
                "quantity": i.quantity,
                "price": str(i.price),
                "per": i.per,
            }
            for i in plan.items.select_related("item").all()
        ],
    }


def _serialize_subscription(sub):
    return {
        "id": sub.id,
        "customer_id": sub.customer_id,
        "customer": sub.customer.name if sub.customer else None,
        "plan_id": sub.subscription_plan_id,
        "plan": sub.subscription_plan.name if sub.subscription_plan else None,
        "start_date": str(sub.start_date),
        "end_date": str(sub.end_date),
        "is_active": sub.is_active,
    }


def _recalculate_plan_price(plan: SubscriptionPlan):
    """
    Recompute total price for the plan following:
    day -> price * qty * plan.days
    week -> price * qty * 4
    month -> price * qty * 1
    """
    total = Decimal("0")
    for plan_item in plan.items.all():
        price = plan_item.price or Decimal("0")
        qty = plan_item.quantity or 0
        per = plan_item.per or "day"

        if per == "day":
            multiplier = Decimal(plan.duration_in_days or 0)
        elif per == "week":
            multiplier = Decimal("4")
        else:
            multiplier = Decimal("1")

        total += price * Decimal(qty) * multiplier

    plan.price = total
    plan.save(update_fields=["price"])


@api_view(["GET"])
def api_subscription_dashboard(request):
    today = timezone.now().date()

    # Same as web view: expired subscriptions are auto-deactivated.
    CustomerSubscription.objects.filter(
        end_date__lt=today,
        is_active=True,
    ).update(is_active=False)

    plans = SubscriptionPlan.objects.prefetch_related("items__item").all()

    active_subscriptions = CustomerSubscription.objects.filter(
        is_active=True,
        end_date__gte=today,
    ).select_related("customer", "subscription_plan")

    de_activated_subscriptions = CustomerSubscription.objects.filter(
        is_active=False,
        end_date__gte=today,
    ).select_related("customer", "subscription_plan")

    expired_subscriptions = CustomerSubscription.objects.filter(
        end_date__lt=today
    ).select_related("customer", "subscription_plan")

    expiring_soon = CustomerSubscription.objects.filter(
        is_active=True,
        end_date__range=[today, today + timezone.timedelta(days=5)],
    ).select_related("customer", "subscription_plan")

    items = Item.objects.all()
    customers = Customer.objects.filter(frozen=False, user_type="user")

    return Response(
        {
            "plans": [_serialize_plan(p) for p in plans],
            "active_subscriptions": [_serialize_subscription(s) for s in active_subscriptions],
            "de_activated_subscriptions": [_serialize_subscription(s) for s in de_activated_subscriptions],
            "expired_subscriptions": [_serialize_subscription(s) for s in expired_subscriptions],
            "expiring_soon": [_serialize_subscription(s) for s in expiring_soon],
            "items": [
                {
                    "id": i.id,
                    "name": i.name,
                    "category": i.category,
                    "selling_price": str(i.selling_price),
                    "buying_price": str(i.buying_price),
                    "mrp": str(i.mrp),
                }
                for i in items
            ],
            "customers": [
                {
                    "id": c.id,
                    "name": c.name,
                    "phone": c.phone,
                    "area": c.area,
                }
                for c in customers
            ],
            "total_active": active_subscriptions.count(),
            "total_expired": expired_subscriptions.count(),
            "total_plans": plans.count(),
            "expiring_count": expiring_soon.count(),
        }
    )


@api_view(["GET"])
def api_get_plans(request):
    plans = SubscriptionPlan.objects.prefetch_related("items__item").all()
    return Response([_serialize_plan(p) for p in plans])


@api_view(["POST"])
def api_create_plan(request):
    name = request.data.get("name")
    duration_in_days = request.data.get("duration_in_days", request.data.get("duration_days"))
    description = request.data.get("description")

    if not name or not duration_in_days:
        return Response(
            {"success": False, "message": "name and duration_in_days are required"},
            status=400,
        )

    plan = SubscriptionPlan.objects.create(
        name=name,
        price=0,
        duration_in_days=duration_in_days,
        description=description,
    )
    return Response(
        {
            "success": True,
            "message": "Subscription plan created successfully",
            "plan_id": plan.id,
        }
    )


@api_view(["POST"])
def api_edit_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)

    plan.name = request.data.get("name", plan.name)
    plan.duration_in_days = request.data.get("duration_days", plan.duration_in_days)
    plan.description = request.data.get("description", plan.description)
    plan.save()
    _recalculate_plan_price(plan)

    return Response(
        {
            "success": True,
            "message": "Subscription plan updated successfully",
            "plan_id": plan.id,
        }
    )


@api_view(["POST"])
def api_add_plan_item(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    item_id = request.data.get("item")
    quantity = request.data.get("quantity")
    price = request.data.get("price")
    per = request.data.get("per", "day")

    if not item_id or not quantity or price is None:
        return Response({"success": False, "message": "item, quantity, price and per are required"}, status=400)

    plan_item, _ = SubscriptionItem.objects.update_or_create(
        subscription_plan=plan,
        item_id=item_id,
        defaults={"quantity": quantity, "price": price, "per": per},
    )
    _recalculate_plan_price(plan)

    return Response(
        {
            "success": True,
            "message": "Item added to plan",
            "plan_item_id": plan_item.id,
        }
    )


@api_view(["POST"])
def api_update_plan_item(request, item_id):
    plan_item = get_object_or_404(SubscriptionItem, id=item_id)
    quantity = request.data.get("quantity")
    price = request.data.get("price")
    per = request.data.get("per")
    if quantity is None and price is None and per is None:
        return Response({"success": False, "message": "quantity, price or per is required"}, status=400)

    if quantity is not None:
        plan_item.quantity = quantity
    if price is not None:
        plan_item.price = price
    if per is not None:
        plan_item.per = per
    plan_item.save()
    _recalculate_plan_price(plan_item.subscription_plan)

    return Response({"success": True, "message": "Item quantity updated"})


@api_view(["POST", "DELETE"])
def api_delete_plan_item(request, item_id):
    plan_item = get_object_or_404(SubscriptionItem, id=item_id)
    plan = plan_item.subscription_plan
    plan_item.delete()
    _recalculate_plan_price(plan)
    return Response({"success": True, "message": "Item removed from plan"})


@api_view(["GET"])
def api_subscription_customers(request):
    customers = Customer.objects.filter(frozen=False, user_type="user")
    return Response(
        [
            {
                "id": c.id,
                "name": c.name,
                "phone": c.phone,
                "area": c.area,
            }
            for c in customers
        ]
    )


@api_view(["POST"])
def api_assign_subscription(request):
    customer_id = request.data.get("customer")
    plan_id = request.data.get("plan")
    start_date = request.data.get("start_date")

    if not customer_id or not plan_id or not start_date:
        return Response(
            {"success": False, "message": "customer, plan and start_date are required"},
            status=400,
        )

    start = _parse_date_yyyy_mm_dd(start_date)
    if start is None:
        return Response({"success": False, "message": "start_date must be YYYY-MM-DD"}, status=400)

    # Kept exactly as web flow: fixed 30-day window.
    end = start + timezone.timedelta(days=30)

    get_object_or_404(SubscriptionPlan, id=plan_id)
    get_object_or_404(Customer, id=customer_id)

    sub = CustomerSubscription.objects.create(
        customer_id=customer_id,
        subscription_plan_id=plan_id,
        start_date=start,
        end_date=end,
        is_active=True,
    )
    return Response(
        {
            "success": True,
            "message": "Subscription assigned successfully",
            "subscription_id": sub.id,
        }
    )


@api_view(["GET"])
def api_customer_subscriptions(request):
    customer_id = request.GET.get("customer")
    subs = CustomerSubscription.objects.select_related("customer", "subscription_plan")
    if customer_id:
        subs = subs.filter(customer_id=customer_id)
    return Response([_serialize_subscription(s) for s in subs])


@api_view(["GET"])
def api_customer_subscription_history(request):
    customer_id = request.GET.get("customer")
    plan_id = request.GET.get("plan")

    subscriptions = CustomerSubscription.objects.select_related("customer", "subscription_plan")
    payments = UserPayment.objects.select_related("user", "subscription")

    if customer_id:
        subscriptions = subscriptions.filter(customer_id=customer_id)
        payments = payments.filter(user_id=customer_id)

    if plan_id:
        subscriptions = subscriptions.filter(subscription_plan_id=plan_id)

    customers = Customer.objects.all()
    plans = SubscriptionPlan.objects.all()

    return Response(
        {
            "subscriptions": [_serialize_subscription(s) for s in subscriptions],
            "payments": [
                {
                    "id": p.id,
                    "user_id": p.user_id,
                    "user_name": p.user.name if p.user else None,
                    "subscription_id": p.subscription_id,
                    "amount": str(p.amount),
                    "transaction_id": p.transaction_id,
                    "method": p.method,
                    "status": p.status,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in payments
            ],
            "customers": [
                {"id": c.id, "name": c.name, "phone": c.phone}
                for c in customers
            ],
            "plans": [
                {"id": p.id, "name": p.name}
                for p in plans
            ],
        }
    )


@api_view(["POST"])
def api_toggle_subscription(request, subscription_id):
    subscription = get_object_or_404(CustomerSubscription, id=subscription_id)
    subscription.is_active = not subscription.is_active
    subscription.save()

    status = "activated" if subscription.is_active else "deactivated"
    return Response(
        {
            "success": True,
            "message": f"Subscription {status} for {subscription.customer.name}",
            "is_active": subscription.is_active,
        }
    )


@api_view(["POST"])
def api_record_subscription_payment(request, subscription_id):
    subscription = get_object_or_404(CustomerSubscription, id=subscription_id)

    amount = request.data.get("amount")
    method = request.data.get("method")
    transaction_id = request.data.get("transaction_id")

    if not amount or not method or not transaction_id:
        return Response(
            {
                "success": False,
                "message": "amount, method and transaction_id are required",
            },
            status=400,
        )

    payment = UserPayment.objects.create(
        subscription=subscription,
        user=subscription.customer,
        amount=amount,
        transaction_id=transaction_id,
        method=method,
        status="SUCCESS",
    )
    return Response(
        {
            "success": True,
            "message": "Payment recorded successfully",
            "payment_id": payment.id,
        }
    )


@api_view(["GET"])
def api_today_deliveries(request):
    today = timezone.now().date()
    deliveries = CustomerSubscription.objects.filter(
        is_active=True,
        end_date__gte=today,
    ).select_related("customer", "subscription_plan")

    return Response(
        [
            {
                "subscription_id": d.id,
                "customer_id": d.customer_id,
                "customer": d.customer.name,
                "phone": d.customer.phone,
                "plan_id": d.subscription_plan_id,
                "plan": d.subscription_plan.name,
                "start_date": str(d.start_date),
                "end_date": str(d.end_date),
            }
            for d in deliveries
        ]
    )
