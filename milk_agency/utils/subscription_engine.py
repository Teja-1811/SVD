from django.utils import timezone
from milk_agency.models import Subscription, SubscriptionItem, SubscriptionOrder


def generate_daily_subscription_orders():

    today = timezone.now().date()

    subscriptions = Subscription.objects.filter(
        active=True,
        start_date__lte=today,
        end_date__gte=today
    ).select_related("customer", "plan")

    created_orders = 0

    for sub in subscriptions:

        plan_items = SubscriptionItem.objects.filter(
            subscription_plan=sub.plan
        ).select_related("item")

        for plan_item in plan_items:

            order, created = SubscriptionOrder.objects.get_or_create(
                subscription=sub,
                customer=sub.customer,
                item=plan_item.item,
                date=today,
                defaults={
                    "quantity": plan_item.quantity
                }
            )

            if created:
                created_orders += 1

    return created_orders