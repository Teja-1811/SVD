from decimal import Decimal

from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from customer_portal.models import CustomerOrder
from milk_agency.models import Bill, Contact, CustomerSubscription, Offers, OrderDelivery, SubscriptionOrder


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def customer_dashboard_api(request):
    customer = request.user
    today = timezone.localdate()

    current_month_bills = Bill.objects.filter(
        customer=customer,
        is_deleted=False,
        invoice_date__year=today.year,
        invoice_date__month=today.month,
    ).order_by("-invoice_date")
    latest_bill = current_month_bills.first()
    latest_order = CustomerOrder.objects.filter(customer=customer).order_by("-created_at", "-id").first()
    latest_delivery = OrderDelivery.objects.filter(order__customer=customer).select_related("order").order_by("-updated_at").first()
    active_subscription = CustomerSubscription.objects.filter(
        customer=customer,
        is_active=True,
        end_date__gte=today,
    ).select_related("subscription_plan").order_by("end_date").first()
    next_subscription_delivery = SubscriptionOrder.objects.filter(
        customer=customer,
        date__gte=today,
    ).select_related("item", "delivery_tracking").order_by("date", "id").first()
    active_offers = Offers.objects.filter(
        offer_for="retailer",
        is_active=True,
        start_date__lte=today,
        end_date__gte=today,
    ).order_by("end_date", "name")[:3]

    actual_due = Decimal(customer.get_actual_due() or 0)
    outstanding_due = actual_due if actual_due > 0 else Decimal("0.00")
    wallet_balance = abs(actual_due) if actual_due < 0 else Decimal("0.00")
    monthly_spend = sum(Decimal(bill.total_amount or 0) for bill in current_month_bills)

    return Response(
        {
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "shop_name": customer.shop_name or "",
                "phone": customer.phone,
                "area": customer.area or "",
                "city": customer.city or "",
                "state": customer.state or "",
                "pin_code": customer.pin_code or "",
                "account_status": "Active" if customer.is_active and not customer.frozen else "Inactive",
                "frozen": customer.frozen,
            },
            "summary": {
                "balance": float(actual_due),
                "outstanding_due": float(outstanding_due),
                "wallet_balance": float(wallet_balance),
                "monthly_invoice_count": current_month_bills.count(),
                "monthly_spend": float(monthly_spend),
                "active_tickets": Contact.objects.filter(customer=customer, status="active").count(),
            },
            "latest_bill": (
                {
                    "bill_id": latest_bill.id,
                    "invoice_number": latest_bill.invoice_number,
                    "invoice_date": str(latest_bill.invoice_date),
                    "total_amount": float(latest_bill.total_amount or 0),
                }
                if latest_bill
                else None
            ),
            "latest_order": (
                {
                    "order_id": latest_order.id,
                    "order_number": latest_order.order_number,
                    "order_date": str(latest_order.order_date),
                    "delivery_date": str(latest_order.delivery_date),
                    "status": latest_order.status,
                    "total_amount": float(latest_order.total_amount or 0),
                    "approved_total_amount": float(latest_order.approved_total_amount or 0),
                    "delivery_charge": float(latest_order.delivery_charge or 0),
                    "payment_status": latest_order.payment_status,
                }
                if latest_order
                else None
            ),
            "latest_delivery": (
                {
                    "delivery_id": latest_delivery.id,
                    "order_id": latest_delivery.order_id,
                    "status": latest_delivery.status,
                    "eta": latest_delivery.eta.isoformat() if latest_delivery.eta else None,
                    "delivered_at": latest_delivery.delivered_at.isoformat() if latest_delivery.delivered_at else None,
                    "notes": latest_delivery.notes or "",
                }
                if latest_delivery
                else None
            ),
            "active_subscription": (
                {
                    "subscription_id": active_subscription.id,
                    "plan_name": active_subscription.subscription_plan.name if active_subscription.subscription_plan else "",
                    "start_date": str(active_subscription.start_date),
                    "end_date": str(active_subscription.end_date),
                }
                if active_subscription
                else None
            ),
            "next_subscription_delivery": (
                {
                    "subscription_order_id": next_subscription_delivery.id,
                    "date": str(next_subscription_delivery.date),
                    "item_name": next_subscription_delivery.item.name if next_subscription_delivery.item else "",
                    "quantity": next_subscription_delivery.quantity,
                    "status": (
                        next_subscription_delivery.delivery_tracking.status
                        if getattr(next_subscription_delivery, "delivery_tracking", None)
                        else ("delivered" if next_subscription_delivery.delivered else "pending")
                    ),
                }
                if next_subscription_delivery
                else None
            ),
            "active_offers": [
                {
                    "id": offer.id,
                    "name": offer.name,
                    "offer_type": offer.offer_type,
                    "price": float(offer.price or 0),
                    "end_date": str(offer.end_date),
                }
                for offer in active_offers
            ],
        },
        status=200,
    )
