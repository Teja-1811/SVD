import json
from collections import OrderedDict
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from api.order_creator import ACTIVE_ORDER_STATUSES, create_or_replace_order
from api.paytm import PaytmConfigError, PaytmGatewayError, build_paytm_form_checkout
from api.user_api_helpers import get_active_offers, get_latest_subscription
from customer_portal.models import CustomerOrder, CustomerOrderItem
from milk_agency.models import Bill, Item, SubscriptionItem
from milk_agency.order_pricing import get_customer_unit_price


USER_COMPANY_NAME = "Dodla"


def user_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if getattr(request.user, "user_type", "").lower() != "user":
            return redirect("customer_portal:home")
        return view_func(request, *args, **kwargs)

    return _wrapped


def user_catalog_queryset(*, include_out_of_stock=False):
    queryset = Item.objects.select_related("company").filter(
        frozen=False,
        company__name__iexact=USER_COMPANY_NAME,
    )
    if not include_out_of_stock:
        queryset = queryset.filter(stock_quantity__gt=0)
    return queryset.order_by("category", "name", "id")


def grouped_catalog(customer, *, include_out_of_stock=False):
    grouped = OrderedDict()
    for item in user_catalog_queryset(include_out_of_stock=include_out_of_stock):
        item.display_price = get_customer_unit_price(item, customer)
        item.in_stock = item.stock_quantity > 0
        category = item.category or "Other"
        grouped.setdefault(category, []).append(item)
    return grouped


def active_orders(customer):
    return (
        CustomerOrder.objects.filter(customer=customer, status__in=ACTIVE_ORDER_STATUSES)
        .prefetch_related("items__item")
        .order_by("delivery_date", "-created_at", "-id")
    )


def latest_bills(customer, *, limit=None):
    queryset = Bill.objects.filter(customer=customer, is_deleted=False).order_by("-invoice_date", "-id")
    if limit:
        return queryset[:limit]
    return queryset


def subscription_context(customer):
    subscription = get_latest_subscription(customer, active_only=True)
    items = []
    if subscription:
        items = SubscriptionItem.objects.filter(
            subscription_plan=subscription.subscription_plan
        ).select_related("item")
    return subscription, items


def offers_context():
    return get_active_offers(offer_for="user")


def profile_completion(customer):
    fields = [
        customer.name,
        customer.phone,
        customer.flat_number,
        customer.area,
        customer.city,
        customer.state,
        customer.pin_code,
    ]
    return round((sum(1 for value in fields if value) / len(fields)) * 100)


def parse_delivery_date(raw_value):
    today = timezone.localdate()
    if not raw_value:
        return today, False

    try:
        delivery_date = datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Invalid delivery date.") from exc

    return delivery_date, delivery_date != today


def minimum_prebook_date():
    return timezone.localdate() + timedelta(days=2)


def validate_order_payload(raw_items, *, is_prebooking):
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("Please select at least one item.")

    normalized = {}
    valid_products = {
        item.id: item
        for item in user_catalog_queryset(include_out_of_stock=True)
    }

    for entry in raw_items:
        try:
            item_id = int(entry.get("item_id"))
            quantity = int(entry.get("quantity", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid product selection.") from exc

        if quantity <= 0:
            raise ValueError("Quantities must be greater than zero.")
        if item_id not in valid_products:
            raise ValueError("One or more selected products are unavailable.")

        normalized.setdefault(item_id, {"item_id": item_id, "quantity": 0})
        normalized[item_id]["quantity"] += quantity

    if not is_prebooking:
        for item_id, entry in normalized.items():
            product = valid_products[item_id]
            if product.stock_quantity <= 0:
                raise ValueError(f"{product.name} is out of stock.")
            if entry["quantity"] > product.stock_quantity:
                raise ValueError(f"Only {product.stock_quantity} unit(s) available for {product.name}.")

    return list(normalized.values())


def save_user_order(customer, raw_items, raw_delivery_date):
    delivery_date, is_prebooking = parse_delivery_date(raw_delivery_date)
    if is_prebooking and delivery_date < minimum_prebook_date():
        raise ValueError("Pre-booking is allowed only from 2 days ahead.")

    normalized_items = validate_order_payload(raw_items, is_prebooking=is_prebooking)
    return create_or_replace_order(
        customer=customer,
        items=normalized_items,
        delivery_date_str=raw_delivery_date or None,
    )


def prepare_user_payment_order(customer, raw_items, raw_delivery_date, *, payment_method="PAYTM"):
    delivery_date, is_prebooking = parse_delivery_date(raw_delivery_date)
    if is_prebooking and delivery_date < minimum_prebook_date():
        raise ValueError("Pre-booking is allowed only from 2 days ahead.")

    normalized_items = validate_order_payload(raw_items, is_prebooking=is_prebooking)
    return create_or_replace_order(
        customer=customer,
        items=normalized_items,
        delivery_date_str=raw_delivery_date or None,
        initial_status="payment_pending",
        payment_method=payment_method,
    )


def save_user_order_response(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request."}, status=400)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)

    try:
        order = save_user_order(
            customer=request.user,
            raw_items=payload.get("items", []),
            raw_delivery_date=str(payload.get("delivery_date") or "").strip(),
        )
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=500)

    return JsonResponse(
        {
            "success": True,
            "order_number": order.order_number,
            "delivery_date": str(order.delivery_date),
            "is_prebooking": order.delivery_date > timezone.localdate(),
            "message": "Pre-booking saved successfully." if order.delivery_date > timezone.localdate() else "Order saved successfully.",
        }
    )


def prepare_user_payment_order_response(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request."}, status=400)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)

    try:
        order = prepare_user_payment_order(
            customer=request.user,
            raw_items=payload.get("items", []),
            raw_delivery_date=str(payload.get("delivery_date") or "").strip(),
            payment_method=str(payload.get("payment_method") or "PAYTM").strip() or "PAYTM",
        )
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=500)

    grand_total = Decimal(order.total_amount or 0) + Decimal(order.delivery_charge or 0)
    payment_method = (order.payment_method or "").upper()
    if payment_method == "PAYTM":
        gateway_order_id = f"{order.order_number}-{timezone.now().strftime('%H%M%S%f')}"[:64]
        if order.gateway_order_id != gateway_order_id:
            order.gateway_order_id = gateway_order_id
            order.save(update_fields=["gateway_order_id", "updated_at"])
        try:
            checkout = build_paytm_form_checkout(request, order, amount=grand_total)
        except (PaytmConfigError, PaytmGatewayError, AttributeError) as exc:
            return JsonResponse({"success": False, "message": str(exc)}, status=400)

    return JsonResponse(
        {
            "success": True,
            "order_id": order.id,
            "order_number": order.order_number,
            "delivery_date": str(order.delivery_date),
            "payment_method": order.payment_method,
            "items_total": float(order.total_amount),
            "delivery_charge": float(order.delivery_charge),
            "grand_total": float(grand_total),
            "paytm_url": checkout.get("gateway_url", "") if payment_method == "PAYTM" else "",
            "paytm_params": checkout.get("params", {}) if payment_method == "PAYTM" else {},
            "paytm_redirect_url": (
                reverse("users:paytm_checkout", kwargs={"order_id": order.id}) if payment_method == "PAYTM" else ""
            ),
            "message": "Payment order prepared successfully.",
        }
    )


def dashboard_cards(customer):
    today = timezone.localdate()
    orders = list(active_orders(customer))
    subscription, subscription_items = subscription_context(customer)
    bills = latest_bills(customer, limit=3)
    return {
        "actual_due": Decimal(customer.get_actual_due() or 0),
        "available_item_count": user_catalog_queryset(include_out_of_stock=False).count(),
        "today_order_count": len([order for order in orders if order.delivery_date == today]),
        "prebook_order_count": len([order for order in orders if order.delivery_date >= minimum_prebook_date()]),
        "latest_order": CustomerOrder.objects.filter(customer=customer).order_by("-delivery_date", "-created_at", "-id").first(),
        "recent_bills": bills,
        "offers": offers_context()[:3],
        "subscription": subscription,
        "subscription_items": subscription_items,
        "profile_completion": profile_completion(customer),
        "primary_address": ", ".join(
            filter(None, [customer.flat_number, customer.area, customer.city, customer.state, customer.pin_code])
        ),
    }
