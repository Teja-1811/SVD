from decimal import Decimal

from django.db.models import ExpressionWrapper, F, Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from customer_portal.models import CustomerOrder
from milk_agency.models import (
    Bill,
    Contact,
    Customer,
    CustomerPayment,
    CustomerSubscription,
    Item,
    LeakageEntry,
    Offers,
    StockInEntry,
    SubscriptionOrder,
)


def _as_float(value):
    return float(value or 0)


def _sum_customer_actual_due(queryset):
    total = Decimal("0.00")
    for customer in queryset:
        total += Decimal(customer.get_actual_due() or 0)
    return total


@api_view(["GET"])
def dashboard_api(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    next_month = (month_start.replace(day=28) + timezone.timedelta(days=4)).replace(day=1)
    year_start = today.replace(month=1, day=1)

    active_customers_qs = Customer.objects.filter(frozen=False)
    retailer_qs = active_customers_qs.filter(user_type="retailer")
    user_qs = active_customers_qs.filter(user_type="user")
    delivery_qs = active_customers_qs.filter(user_type="delivery")

    total_customers = Customer.objects.count()
    active_customers = active_customers_qs.count()
    frozen_customers = Customer.objects.filter(frozen=True).count()

    total_items = Item.objects.count()
    active_items = Item.objects.filter(frozen=False).count()
    low_stock_items = Item.objects.filter(frozen=False, stock_quantity__lt=F("pcs_count")).count()
    out_of_stock_items = Item.objects.filter(stock_quantity=0).count()

    stock_value = Item.objects.annotate(
        stock_value=ExpressionWrapper(
            F("stock_quantity") * F("buying_price"),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    ).aggregate(
        total=Coalesce(Sum("stock_value"), Value(Decimal("0.00")), output_field=DecimalField(max_digits=14, decimal_places=2))
    )["total"]

    today_bills = Bill.objects.filter(is_deleted=False, invoice_date=today)
    monthly_bills = Bill.objects.filter(is_deleted=False, invoice_date__gte=month_start, invoice_date__lt=next_month)
    yearly_bills = Bill.objects.filter(is_deleted=False, invoice_date__gte=year_start, invoice_date__lte=today)

    sales_today = today_bills.aggregate(total=Coalesce(Sum("total_amount"), Value(Decimal("0.00"))))["total"]
    sales_month = monthly_bills.aggregate(total=Coalesce(Sum("total_amount"), Value(Decimal("0.00"))))["total"]
    sales_year = yearly_bills.aggregate(total=Coalesce(Sum("total_amount"), Value(Decimal("0.00"))))["total"]
    profit_today = today_bills.aggregate(total=Coalesce(Sum("profit"), Value(Decimal("0.00"))))["total"]

    total_dues = _sum_customer_actual_due(Customer.objects.all())
    due_customers = []
    for customer in Customer.objects.filter(frozen=False).order_by("name"):
        actual_due = Decimal(customer.get_actual_due() or 0)
        if actual_due > 0:
            due_customers.append(
                {
                    "id": customer.id,
                    "name": customer.name,
                    "phone": customer.phone,
                    "actual_due": float(actual_due),
                }
            )
    due_customers = sorted(due_customers, key=lambda item: item["actual_due"], reverse=True)

    pending_orders_qs = CustomerOrder.objects.select_related("customer").filter(
        status__in=["pending", "payment_pending", "confirmed"]
    ).order_by("delivery_date", "-created_at")
    today_orders_qs = CustomerOrder.objects.filter(delivery_date=today)
    today_order_sales = today_orders_qs.aggregate(
        total=Coalesce(Sum("approved_total_amount"), Value(Decimal("0.00")))
    )["total"]

    customers_no_orders_today_qs = retailer_qs.exclude(
        id__in=CustomerOrder.objects.filter(order_date=today).values_list("customer_id", flat=True)
    ).order_by("name")

    active_enquiries_qs = Contact.objects.filter(status="active").order_by("-created_at")
    resolved_enquiries_count = Contact.objects.filter(status="resolved").count()

    active_subscriptions_qs = CustomerSubscription.objects.filter(
        is_active=True,
        end_date__gte=today,
    ).select_related("customer", "subscription_plan")
    expiring_subscriptions_qs = active_subscriptions_qs.filter(
        end_date__range=[today, today + timezone.timedelta(days=5)]
    )
    today_subscription_orders_qs = SubscriptionOrder.objects.filter(date=today)
    delivered_subscription_orders_qs = today_subscription_orders_qs.filter(delivered=True)

    active_offers_qs = Offers.objects.filter(
        is_active=True,
        start_date__lte=today,
        end_date__gte=today,
    ).order_by("end_date", "name")

    today_payments_qs = CustomerPayment.objects.filter(created_at__date=today, status__iexact="SUCCESS")
    payment_total_today = today_payments_qs.aggregate(
        total=Coalesce(Sum("amount"), Value(Decimal("0.00")))
    )["total"]

    stock_in_today_qs = StockInEntry.objects.filter(date=today)
    leakage_month_qs = LeakageEntry.objects.filter(date__year=today.year, date__month=today.month)
    stock_in_today_value = stock_in_today_qs.aggregate(
        total=Coalesce(Sum("value"), Value(Decimal("0.00")))
    )["total"]
    leakage_month_loss = leakage_month_qs.aggregate(
        total=Coalesce(Sum("total_loss"), Value(Decimal("0.00")))
    )["total"]

    top_stock_items = list(
        Item.objects.annotate(
            stock_value=ExpressionWrapper(
                F("stock_quantity") * F("buying_price"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .select_related("company")
        .order_by("-stock_value", "name")
        .values(
            "id",
            "name",
            "stock_quantity",
            "pcs_count",
            "category",
            company_name=F("company__name"),
            stock_value=F("stock_value"),
        )[:5]
    )

    top_selling_items_today = list(
        today_bills.values(item_id=F("items__item_id"), item_name=F("items__item__name"))
        .annotate(quantity=Coalesce(Sum("items__quantity"), 0), amount=Coalesce(Sum("items__total_amount"), 0))
        .exclude(item_id__isnull=True)
        .order_by("-quantity", "-amount")[:5]
    )

    payload = {
        "date": str(today),
        "summary": {
            "customers": total_customers,
            "active_customers": active_customers,
            "frozen_customers": frozen_customers,
            "retailers": retailer_qs.count(),
            "users": user_qs.count(),
            "delivery_users": delivery_qs.count(),
            "items": total_items,
            "active_items": active_items,
            "sales_today": _as_float(sales_today),
            "sales_month": _as_float(sales_month),
            "sales_year": _as_float(sales_year),
            "profit_today": _as_float(profit_today),
            "dues": _as_float(total_dues),
            "stock_value": _as_float(stock_value),
            "low_stock_items": low_stock_items,
            "out_of_stock_items": out_of_stock_items,
            "pending_orders": pending_orders_qs.count(),
            "today_orders": today_orders_qs.count(),
            "today_order_sales": _as_float(today_order_sales),
            "active_enquiries": active_enquiries_qs.count(),
            "resolved_enquiries": resolved_enquiries_count,
            "active_subscriptions": active_subscriptions_qs.count(),
            "expiring_subscriptions": expiring_subscriptions_qs.count(),
            "active_offers": active_offers_qs.count(),
            "payments_today_total": _as_float(payment_total_today),
            "payments_today_count": today_payments_qs.count(),
            "stock_in_today_value": _as_float(stock_in_today_value),
            "stock_in_today_entries": stock_in_today_qs.count(),
            "leakage_month_loss": _as_float(leakage_month_loss),
            "today_subscription_orders": today_subscription_orders_qs.count(),
            "today_subscription_delivered": delivered_subscription_orders_qs.count(),
            "customers_no_orders_today_count": customers_no_orders_today_qs.count(),
        },
        "pending_orders_preview": [
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "customer_name": order.customer.name if order.customer else "",
                "phone": order.customer.phone if order.customer else "",
                "status": order.status,
                "delivery_date": str(order.delivery_date),
                "total_amount": _as_float(order.total_amount),
                "approved_total_amount": _as_float(order.approved_total_amount),
                "payment_status": order.payment_status,
            }
            for order in pending_orders_qs[:5]
        ],
        "customers_no_orders_today_list": [
            {
                "id": customer.id,
                "name": customer.name,
                "phone": customer.phone,
                "shop_name": customer.shop_name,
            }
            for customer in customers_no_orders_today_qs[:25]
        ],
        "active_enquiries_preview": [
            {
                "id": enquiry.id,
                "name": enquiry.name,
                "phone": enquiry.phone,
                "subject": enquiry.subject,
                "created_at": enquiry.created_at.isoformat() if enquiry.created_at else None,
            }
            for enquiry in active_enquiries_qs[:5]
        ],
        "active_offers_preview": [
            {
                "id": offer.id,
                "name": offer.name,
                "offer_for": offer.offer_for,
                "offer_type": offer.offer_type,
                "price": _as_float(offer.price),
                "end_date": str(offer.end_date),
            }
            for offer in active_offers_qs[:5]
        ],
        "expiring_subscriptions_preview": [
            {
                "id": sub.id,
                "customer_name": sub.customer.name if sub.customer else "",
                "phone": sub.customer.phone if sub.customer else "",
                "plan_name": sub.subscription_plan.name if sub.subscription_plan else "",
                "end_date": str(sub.end_date),
                "days_left": (sub.end_date - today).days,
            }
            for sub in expiring_subscriptions_qs.order_by("end_date")[:5]
        ],
        "top_due_customers": due_customers[:5],
        "top_stock_items": [
            {
                **item,
                "stock_value": _as_float(item["stock_value"]),
            }
            for item in top_stock_items
        ],
        "top_selling_items_today": [
            {
                "item_id": item["item_id"],
                "item_name": item["item_name"],
                "quantity": _as_float(item["quantity"]),
                "amount": _as_float(item["amount"]),
            }
            for item in top_selling_items_today
        ],
    }

    return Response(payload)
