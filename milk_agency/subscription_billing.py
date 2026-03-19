from calendar import monthrange
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from milk_agency.models import (
    Bill,
    BillItem,
    CustomerSubscription,
    SubscriptionDelivery,
    SubscriptionItem,
    SubscriptionOrder,
)


def _build_invoice_number():
    base = timezone.now().strftime("INV-%Y%m%d%H%M%S")
    invoice_number = base
    suffix = 1
    while Bill.objects.filter(invoice_number=invoice_number).exists():
        invoice_number = f"{base}-{suffix}"
        suffix += 1
    return invoice_number


def _is_subscription_paused(subscription, target_date):
    return subscription.pauses.filter(
        pause_date__lte=target_date,
        is_resumed=False,
    ).exists() or subscription.pauses.filter(
        pause_date__lte=target_date,
        is_resumed=True,
        resume_date__gt=target_date,
    ).exists()


def _is_plan_item_due(subscription, plan_item, target_date):
    start_date = subscription.start_date
    if target_date < start_date:
        return False

    per = (plan_item.per or "day").lower()
    if per == "day":
        return True

    if per == "week":
        delta_days = (target_date - start_date).days
        return delta_days % 7 == 0

    start_dom = start_date.day
    last_dom = monthrange(target_date.year, target_date.month)[1]
    expected_dom = min(start_dom, last_dom)
    return target_date.day == expected_dom


def generate_daily_subscription_orders(target_date=None):
    target_date = target_date or timezone.localdate()

    subscriptions = (
        CustomerSubscription.objects.filter(
            is_active=True,
            start_date__lte=target_date,
            end_date__gte=target_date,
        )
        .select_related("customer", "subscription_plan")
        .prefetch_related("subscription_plan__items", "pauses")
    )

    created_orders = 0

    for subscription in subscriptions:
        if _is_subscription_paused(subscription, target_date):
            continue

        for plan_item in subscription.subscription_plan.items.select_related("item").all():
            if not _is_plan_item_due(subscription, plan_item, target_date):
                continue

            _, created = SubscriptionOrder.objects.get_or_create(
                subscription=subscription,
                customer=subscription.customer,
                item=plan_item.item,
                date=target_date,
                defaults={"quantity": plan_item.quantity},
            )
            if created:
                created_orders += 1

    return created_orders


def _get_subscription_item(order):
    return SubscriptionItem.objects.get(
        subscription_plan=order.subscription.subscription_plan,
        item=order.item,
    )


def _get_existing_bill_for_customer(customer, target_date):
    delivery = (
        SubscriptionDelivery.objects.select_related("bill")
        .filter(
            subscription_order__customer=customer,
            subscription_order__date=target_date,
            bill__isnull=False,
        )
        .order_by("bill_id")
        .first()
    )
    return delivery.bill if delivery else None


def generate_subscription_delivery_bills(target_date=None):
    target_date = target_date or timezone.localdate()
    generate_daily_subscription_orders(target_date)

    deliveries = (
        SubscriptionDelivery.objects.select_related(
            "subscription_order__customer",
            "subscription_order__subscription__subscription_plan",
            "subscription_order__item",
        )
        .filter(subscription_order__date=target_date)
        .order_by("subscription_order__customer__name", "subscription_order__id")
    )

    deliveries_by_customer = defaultdict(list)
    for delivery in deliveries:
        deliveries_by_customer[delivery.subscription_order.customer_id].append(delivery)

    created_bills = 0
    linked_deliveries = 0

    for customer_deliveries in deliveries_by_customer.values():
        unbilled_deliveries = [delivery for delivery in customer_deliveries if delivery.bill_id is None]
        if not unbilled_deliveries:
            continue

        customer = customer_deliveries[0].subscription_order.customer

        with transaction.atomic():
            bill = _get_existing_bill_for_customer(customer, target_date)
            if bill is None:
                bill = Bill.objects.create(
                    customer=customer,
                    invoice_number=_build_invoice_number(),
                    invoice_date=target_date,
                    total_amount=Decimal("0.00"),
                    op_due_amount=customer.due,
                    last_paid=Decimal("0.00"),
                    profit=Decimal("0.00"),
                )
                created_bills += 1

            total_increment = Decimal("0.00")
            profit_increment = Decimal("0.00")

            for delivery in unbilled_deliveries:
                order = delivery.subscription_order
                plan_item = _get_subscription_item(order)
                price = Decimal(plan_item.price or 0)
                qty = Decimal(order.quantity or 0)
                line_total = price * qty
                line_profit = (Decimal(order.item.selling_price) - Decimal(order.item.buying_price)) * qty

                BillItem.objects.create(
                    bill=bill,
                    item=order.item,
                    price_per_unit=price,
                    discount=Decimal("0.00"),
                    quantity=order.quantity,
                    total_amount=line_total,
                )

                order.item.stock_quantity -= order.quantity
                order.item.save(update_fields=["stock_quantity"])

                delivery.bill = bill
                delivery.save(update_fields=["bill"])

                total_increment += line_total
                profit_increment += line_profit
                linked_deliveries += 1

            bill.total_amount = (bill.total_amount or Decimal("0.00")) + total_increment
            bill.profit = (bill.profit or Decimal("0.00")) + profit_increment
            bill.save(update_fields=["total_amount", "profit"])

            customer.due = customer.get_actual_due()
            customer.save(update_fields=["due"])

    return {
        "date": target_date,
        "created_bills": created_bills,
        "linked_deliveries": linked_deliveries,
    }
