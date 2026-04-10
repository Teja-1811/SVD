from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.db import OperationalError, ProgrammingError, transaction
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.utils import timezone
from datetime import time
from decimal import Decimal
import json

from api.order_creator import can_delete_order, delete_order as delete_customer_order
from milk_agency.models import (
    Bill,
    Customer,
    CustomerPayment,
    CustomerSubscription,
    Item,
    Offers,
    OrderDelivery,
    SubscriptionOrder,
)
from milk_agency.order_pricing import DELIVERY_ITEM_CODE, get_customer_unit_price, get_delivery_charge_amount
from milk_agency.push_notifications import notify_admin_order_placed, notify_admin_payment_recorded, notify_admin_profile_updated



from .models import CustomerOrder, CustomerOrderItem
from milk_agency.models import CustomerPayment


def _find_linked_customer_order_for_bill(bill):
    orders = CustomerOrder.objects.filter(
        customer=bill.customer,
        order_date=bill.invoice_date
    ).order_by('-id')
    for order in orders:
        if Decimal(order.approved_total_amount or 0) + Decimal(order.delivery_charge or 0) == Decimal(bill.total_amount or 0):
            return order
        if Decimal(order.approved_total_amount or 0) == Decimal(bill.total_amount or 0):
            return order
    return orders.first()


def _latest_due_bill_for_customer(customer):
    bills = (
        Bill.objects.filter(customer=customer, is_deleted=False)
        .order_by("-invoice_date", "-id")
    )
    for bill in bills:
        total_amount = Decimal(bill.total_amount or 0)
        paid_amount = Decimal(bill.last_paid or 0)
        if total_amount - paid_amount > 0:
            return bill
    return None


def _latest_order_for_customer(customer):
    return (
        CustomerOrder.objects.filter(customer=customer)
        .order_by("-order_date", "-id")
        .first()
    )


def _recalculate_bill_last_paid(bill):
    if not bill:
        return

    total_paid = CustomerPayment.objects.filter(
        bill=bill,
        status="SUCCESS",
    ).aggregate(
        total=Coalesce(
            Sum("amount"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )["total"]
    bill.last_paid = total_paid
    bill.save(update_fields=["last_paid"])


def _record_gateway_due_payment(customer, bill, amount, *, transaction_id, payment_method="gateway", gateway_transaction_id=None, payment_order_id=None):
    """
    Records gateway payment using unified CustomerPayment model.
    """
    payment_method = payment_method or "UPI"

    with transaction.atomic():
        payment, created = CustomerPayment.objects.get_or_create(
            transaction_id=transaction_id,
            defaults={
                "customer": customer,
                "bill": bill,
                "amount": amount,
                "method": payment_method,
                "status": "success",
                "gateway_transaction_id": gateway_transaction_id or "",
                "payment_order_id": payment_order_id or "",
            },
        )
        if not created:
            payment.amount = amount
            payment.method = payment_method
            payment.status = "success"
            if gateway_transaction_id:
                payment.gateway_transaction_id = gateway_transaction_id
            if payment_order_id:
                payment.payment_order_id = payment_order_id
            payment.completed_at = timezone.now()
            payment.save(update_fields=["amount", "method", "status", "gateway_transaction_id", "payment_order_id", "completed_at"])

        if bill:
            _recalculate_bill_last_paid(bill)

        customer.due = customer.get_actual_due()
        customer.save(update_fields=["due"])

    transaction.on_commit(lambda payment_id=payment.id: notify_admin_payment_recorded(CustomerPayment.objects.select_related("customer").get(pk=payment_id)))
    return payment


def _safe_first(queryset):
    try:
        return queryset.first()
    except (OperationalError, ProgrammingError):
        return None


def _safe_list(queryset, limit=None):
    try:
        if limit is not None:
            return list(queryset[:limit])
        return list(queryset)
    except (OperationalError, ProgrammingError):
        return []


def _safe_count(queryset):
    try:
        return queryset.count()
    except (OperationalError, ProgrammingError):
        return 0


def _customer_delivery_address(customer):
    return ", ".join(
        filter(
            None,
            [
                customer.flat_number,
                customer.area,
                customer.city,
                customer.state,
                customer.pin_code,
            ],
        )
    ) or "Not provided"


def _normalize_order_items(raw_items):
    if isinstance(raw_items, dict):
        raw_items = list(raw_items.values())
    if not isinstance(raw_items, list):
        return []

    normalized = []
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue

        item_id = entry.get("item_id", entry.get("id"))
        quantity = entry.get("quantity", entry.get("qty", 0))
        normalized.append(
            {
                "item_id": item_id,
                "quantity": quantity,
            }
        )
    return normalized


def _build_order_detail_payload(order_obj):
    subtotal_amount = Decimal(order_obj.approved_total_amount or order_obj.total_amount or 0)
    display_total_amount = subtotal_amount + Decimal(order_obj.delivery_charge or 0)
    savings_amount = max(Decimal(order_obj.total_amount or 0) - subtotal_amount, Decimal("0.00"))
    invoice_download_url = ""
    bill = Bill.objects.filter(
        customer=order_obj.customer,
        total_amount=order_obj.approved_total_amount
    ).order_by('-invoice_date').first()
    if bill:
        invoice_download_url = reverse("milk_agency:generate_invoice_pdf", args=[bill.id])

    return {
        "order": {
            "id": order_obj.id,
            "order_number": order_obj.order_number,
            "status": order_obj.status,
            "order_date": order_obj.order_date,
            "delivery_date": order_obj.delivery_date,
            "delivery_address": order_obj.delivery_address,
            "delivery_charge": Decimal(order_obj.delivery_charge or 0),
            "display_total_amount": display_total_amount,
            "subtotal_amount": subtotal_amount,
            "payment_method": order_obj.payment_method,
            "payment_status": order_obj.payment_status,
            "items": [
                {
                    "name": order_item.item.name if order_item.item else "",
                    "requested_quantity": order_item.requested_quantity,
                    "requested_price": Decimal(order_item.requested_price or 0),
                    "requested_total": Decimal(order_item.requested_total or 0),
                }
                for order_item in order_obj.items.all()
            ],
        },
        "subtotal_amount": subtotal_amount,
        "invoice_download_url": invoice_download_url,
        "savings_amount": savings_amount,
    }


# ======================================================
# LOGIN
# ======================================================
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            messages.error(request, 'Username and password are required.', extra_tags='login')
            return redirect('customer_portal:login')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if isinstance(user, Customer):
                login(request, user, backend='customer_portal.authentication.CustomerBackend')
                if user.is_staff:
                    return redirect('milk_agency:home')
                elif getattr(user, "user_type", "").lower() == "user":
                    return redirect('users:dashboard')
                else:
                    return redirect('customer_portal:home')
            else:
                login(request, user)
                return redirect('milk_agency:home')
        else:
            messages.error(request, 'Invalid username or password.', extra_tags='login')
            return redirect('/')

    return render(request, 'index.html')


# ======================================================
# HOME
# ======================================================
@login_required
@never_cache
def home(request):
    customer = request.user
    today = timezone.localdate()
    account_offer_type = "user" if getattr(customer, "user_type", "").lower() == "user" else "retailer"
    current_month_bills = Bill.objects.filter(
        customer=customer,
        is_deleted=False,
        invoice_date__year=today.year,
        invoice_date__month=today.month,
    ).order_by("-invoice_date")
    monthly_invoice_count = _safe_count(current_month_bills)
    monthly_spend = sum(Decimal(bill.total_amount or 0) for bill in current_month_bills)
    latest_order = (
        CustomerOrder.objects.filter(customer=customer)
        .order_by("-created_at", "-id")
        .first()
    )
    if latest_order:
        latest_order.display_total_amount = Decimal(
            latest_order.approved_total_amount or latest_order.total_amount or 0
        ) + Decimal(latest_order.delivery_charge or 0)

    active_subscription = _safe_first(
        CustomerSubscription.objects.filter(customer=customer, is_active=True, end_date__gte=today)
        .select_related("subscription_plan")
        .order_by("end_date")
    )
    next_subscription_delivery = _safe_first(
        SubscriptionOrder.objects.filter(customer=customer, date__gte=today)
        .select_related("item", "delivery_tracking")
        .order_by("date", "id")
    )
    latest_delivery = _safe_first(
        OrderDelivery.objects.filter(order__customer=customer)
        .select_related("order")
        .order_by("-updated_at")
    )
    active_offers = _safe_list(
        Offers.objects.filter(
            offer_for=account_offer_type,
            is_active=True,
            start_date__lte=today,
            end_date__gte=today,
        ).order_by("end_date", "name"),
        limit=3,
    )

    actual_due = Decimal(customer.get_actual_due() or 0)
    outstanding_due = actual_due if actual_due > 0 else Decimal("0.00")
    wallet_balance = abs(actual_due) if actual_due < 0 else Decimal("0.00")

    profile_fields = [
        customer.name,
        customer.phone,
        customer.flat_number,
        customer.area,
        customer.city,
        customer.state,
        customer.pin_code,
    ]
    profile_completion = round(
        (sum(1 for value in profile_fields if value) / len(profile_fields)) * 100
    )

    context = {
        "actual_due": actual_due,
        "outstanding_due": outstanding_due,
        "wallet_balance": wallet_balance,
        "monthly_invoice_count": monthly_invoice_count,
        "monthly_spend": monthly_spend,
        "latest_bill": _safe_first(current_month_bills),
        "latest_order": latest_order,
        "active_subscription": active_subscription,
        "next_subscription_delivery": next_subscription_delivery,
        "latest_delivery": latest_delivery,
        "active_offers": active_offers,
        "account_offer_type": account_offer_type,
        "profile_completion": profile_completion,
        "primary_address": ", ".join(
            filter(None, [customer.flat_number, customer.area, customer.city, customer.state, customer.pin_code])
        ),
    }
    return render(request, 'customer_portal/home.html', context)


# ======================================================
# CUSTOMER ORDERS DASHBOARD
# ======================================================
@never_cache
@login_required
def customer_orders_dashboard(request):

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            items = _normalize_order_items(data.get('items', []))

            if not items:
                return JsonResponse({'success': False, 'message': 'No items selected'})

            order_number = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}"

            order = CustomerOrder.objects.create(
                order_number=order_number,
                customer=request.user,
                created_by=request.user,
                delivery_date=today,
                delivery_address=_customer_delivery_address(request.user),
            )

            total_amount = 0
            for i in items:
                item = get_object_or_404(Item, id=i["item_id"])
                qty = int(i["quantity"])
                price = get_customer_unit_price(item, request.user)
                line_total = qty * price

                CustomerOrderItem.objects.create(
                    order=order,
                    item=item,
                    requested_quantity=qty,
                    requested_price=price,
                    requested_total=line_total
                )

                total_amount += line_total

            order.delivery_charge = get_delivery_charge_amount(customer=request.user, address=order.delivery_address)
            order.total_amount = total_amount
            order.save()
            transaction.on_commit(lambda order_id=order.id: notify_admin_order_placed(CustomerOrder.objects.select_related("customer").get(pk=order_id)))

            return JsonResponse({'success': True, 'order_number': order_number})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    items = Item.objects.select_related("company").filter(company__name__iexact="Dodla")

    for item in items:
        item.display_price = get_customer_unit_price(item, request.user)
        if item.mrp and item.mrp > 0:
            item.margin_percent = round(((item.mrp - item.selling_price) / item.mrp) * 100, 1)
        else:
            item.margin_percent = 0

    today = timezone.now().date()

    customer_orders = CustomerOrder.objects.filter(
        customer=request.user,
        order_date=today
    ).order_by('-order_date')

    items_by_company = {}

    for item in items:
        company = item.company.name if item.company else "Other"
        category = item.category if item.category else "Other"

        items_by_company.setdefault(company, {}).setdefault(category, []).append(item)

    last_order = CustomerOrder.objects.filter(
        customer=request.user
    ).order_by('-order_date').first()
    if last_order:
        last_order.display_total_amount = Decimal(last_order.total_amount or 0) + Decimal(last_order.delivery_charge or 0)

    return render(request, 'customer_portal/customer_orders_dashboard.html', {
        'items_by_company': items_by_company,
        'customer_orders': customer_orders,
        'last_order': last_order,
    })


# ======================================================
# PLACE ORDER (TIME WINDOW SAFE)
# ======================================================
@csrf_exempt
@login_required
def place_order(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"}, status=400)

    try:
        now = timezone.localtime()
        current_time = now.time()

        start_time = time(7, 0)   # 7 AM
        end_time = time(16, 0)    # 4 PM

        if current_time < start_time or current_time >= end_time:
            return JsonResponse({
                "success": False,
                "message": "Orders allowed only between 7:00 AM and 4:00 PM"
            }, status=403)

        data = json.loads(request.body)
        items = _normalize_order_items(data.get("items", []))

        if not items:
            return JsonResponse({"success": False, "message": "No items selected"}, status=400)

        order_number = f"ORD{now.strftime('%Y%m%d%H%M%S')}"
        customer = request.user

        order = CustomerOrder.objects.create(
            order_number=order_number,
            customer=customer,
            created_by=customer,
            order_date=now.date(),
            delivery_date=now.date(),
            delivery_address=_customer_delivery_address(customer),
        )

        total_amount = 0

        for i in items:
            item = get_object_or_404(Item, id=i["item_id"])
            qty = int(i["quantity"])

            if qty <= 0:
                continue

            price = float(get_customer_unit_price(item, customer))
            line_total = qty * price

            CustomerOrderItem.objects.create(
                order=order,
                item=item,
                requested_quantity=qty,
                requested_price=price,
                requested_total=line_total
            )

            total_amount += line_total

        if total_amount == 0:
            order.delete()
            return JsonResponse({"success": False, "message": "Invalid quantity"}, status=400)

        order.total_amount = total_amount
        order.delivery_charge = get_delivery_charge_amount(customer=customer, address=order.delivery_address)
        order.approved_total_amount = total_amount
        order.save()
        transaction.on_commit(lambda order_id=order.id: notify_admin_order_placed(CustomerOrder.objects.select_related("customer").get(pk=order_id)))

        return JsonResponse({"success": True, "order_number": order_number})

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


# ======================================================
# REPORTS DASHBOARD
# ======================================================
@never_cache
@login_required
def reports_dashboard(request):
    selected_month = request.GET.get('date', timezone.now().strftime('%Y-%m'))
    try:
        year, month = map(int, selected_month.split('-'))
    except:
        year = timezone.now().year
        month = timezone.now().month

    bills = Bill.objects.filter(
        customer=request.user,
        invoice_date__year=year,
        invoice_date__month=month
    ).order_by('-invoice_date')

    total_amount = sum(b.total_amount for b in bills) if bills else 0
    average_amount = total_amount / len(bills) if bills else 0

    return render(request, 'customer_portal/reports_dashboard.html', {
        'bills': bills,
        'selected_date': selected_month,
        'current_year': year,
        'current_month': month,
        'total_amount': total_amount,
        'average_amount': average_amount
    })


# ======================================================
# LAST ORDER DETAILS (SAFE)
# ======================================================
@never_cache
@login_required
def last_order_details(request):
    order_obj = (
        CustomerOrder.objects.filter(customer=request.user)
        .select_related("customer", "bill")
        .prefetch_related("items__item")
        .order_by("-order_date", "-id")
        .first()
    )
    context = {
        "order": None,
        "invoice_download_url": "",
        "savings_amount": Decimal("0.00"),
    }
    if order_obj:
        context.update(_build_order_detail_payload(order_obj))
    return render(request, "customer_portal/last_order_details.html", context)


@never_cache
@login_required
def order_history(request):
    orders = list(
        CustomerOrder.objects.filter(customer=request.user)
        .order_by("-order_date", "-id")
    )
    for order in orders:
        order.display_total_amount = Decimal(order.approved_total_amount or order.total_amount or 0) + Decimal(order.delivery_charge or 0)
    return render(
        request,
        "customer_portal/order_history.html",
        {
            "orders": orders,
        },
    )


@never_cache
@login_required
def order_detail(request, order_id):
    order_obj = get_object_or_404(
        CustomerOrder.objects.filter(customer=request.user)
        .select_related("customer", "bill")
        .prefetch_related("items__item"),
        id=order_id,
    )
    context = _build_order_detail_payload(order_obj)
    return render(request, "customer_portal/order_detail.html", context)


@never_cache
@login_required
def delete_order(request, order_id):
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect("customer_portal:order_history")

    order = get_object_or_404(CustomerOrder.objects.filter(customer=request.user), id=order_id)
    if not can_delete_order(order):
        messages.error(request, "Only payment pending orders can be deleted.")
        return redirect("customer_portal:order_detail", order_id=order_id)

    if delete_customer_order(request.user, order_id):
        messages.success(request, f"Order {order.order_number} deleted successfully.")
        return redirect("customer_portal:order_history")

    messages.error(request, "Unable to delete this order.")
    return redirect("customer_portal:order_detail", order_id=order_id)


# ======================================================
# BILL DETAILS
# ======================================================
@never_cache
@login_required
def bill_details(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id, customer=request.user)
    bill_items = bill.items.all().select_related('item')
    linked_order = _find_linked_customer_order_for_bill(bill)
    delivery_charge_item = bill_items.filter(item__code=DELIVERY_ITEM_CODE).first()
    delivery_charge = Decimal(delivery_charge_item.total_amount if delivery_charge_item else 0)
    if delivery_charge == 0 and linked_order:
        delivery_charge = Decimal(linked_order.delivery_charge or 0)
    display_items = bill_items.exclude(item__code=DELIVERY_ITEM_CODE)

    return render(request, 'customer_portal/bill_details.html', {
        'bill': bill,
        'bill_items': display_items,
        'delivery_charge': delivery_charge,
        'items_subtotal': Decimal(bill.total_amount or 0) - delivery_charge,
    })


# ======================================================
# UPDATE PROFILE
# ======================================================
@never_cache
@login_required
def update_profile(request):
    customer = request.user

    if request.method == 'POST':
        customer.name = request.POST.get('name', customer.name)
        customer.phone = request.POST.get('phone', customer.phone)
        customer.shop_name = request.POST.get('shop_name', customer.shop_name)
        customer.area = request.POST.get('area', customer.area)
        customer.city = request.POST.get('city', customer.city)
        customer.state = request.POST.get('state', customer.state)
        customer.pin_code = request.POST.get('pin_code', customer.pin_code)
        customer.save()
        notify_admin_profile_updated(customer)

        new_password = request.POST.get('new_password')
        if new_password:
            if not customer.check_password(request.POST.get('current_password')):
                messages.error(request, 'Current password incorrect')
                return redirect('customer_portal:update_profile')

            if new_password != request.POST.get('confirm_password'):
                messages.error(request, "Passwords don't match")
                return redirect('customer_portal:update_profile')

            customer.set_password(new_password)
            customer.save()
            messages.success(request, 'Password updated successfully')

        messages.success(request, 'Profile updated successfully')
        return redirect('customer_portal:home')

    return render(request, 'customer_portal/update_profile.html', {'customer': customer})


# ======================================================
# COLLECT PAYMENT
# ======================================================
@login_required
def collect_payment(request):
    customer = request.user
    actual_due = Decimal(customer.get_actual_due() or 0)
    outstanding_due = actual_due if actual_due > 0 else Decimal("0.00")
    wallet_balance = abs(actual_due) if actual_due < 0 else Decimal("0.00")

    payments = (
        CustomerPayment.objects.select_related("bill")
        .filter(customer=customer)
        .order_by("-created_at")
    )
    recent_payments = list(payments[:8])
    successful_payments = payments.filter(status="SUCCESS")
    successful_total = sum(Decimal(payment.amount or 0) for payment in successful_payments)
    latest_order = _latest_order_for_customer(customer)

    bills = (
        Bill.objects.filter(customer=customer, is_deleted=False)
        .order_by("-invoice_date", "-id")
    )
    bill_rows = []
    latest_due_bill = None
    for bill in bills[:8]:
        total_amount = Decimal(bill.total_amount or 0)
        paid_amount = Decimal(bill.last_paid or 0)
        due_amount = max(total_amount - paid_amount, Decimal("0.00"))
        if not latest_due_bill and due_amount > 0:
            latest_due_bill = bill
        bill_rows.append(
            {
                "id": bill.id,
                "invoice_number": bill.invoice_number,
                "invoice_date": bill.invoice_date,
                "total_amount": total_amount,
                "paid_amount": paid_amount,
                "due_amount": due_amount,
                "is_settled": due_amount <= 0,
            }
        )

    recent_orders = list(
        CustomerOrder.objects.filter(customer=customer)
        .order_by("-order_date", "-id")[:6]
    )
    for order in recent_orders:
        order.display_total_amount = Decimal(order.approved_total_amount or order.total_amount or 0) + Decimal(order.delivery_charge or 0)



    context = {
        "actual_due": actual_due,
        "outstanding_due": outstanding_due,
        "wallet_balance": wallet_balance,
        "suggested_upi_amount": outstanding_due if outstanding_due > 0 else Decimal("0.00"),
        "latest_due_bill": latest_due_bill,
        "latest_order": latest_order,
        "recent_payments": recent_payments,
        "payments_count": payments.count(),
        "successful_payment_total": successful_total,
        "bill_rows": bill_rows,
        "recent_orders": recent_orders,
    }
    return render(request, "customer_portal/collect_payment.html", context)


@login_required
def start_collect_payment(request):
    if request.method != "POST":
        return redirect("customer_portal:collect_payment")

    customer = request.user
    raw_amount = (request.POST.get("amount") or "").strip()
    try:
        amount = Decimal(raw_amount)
    except Exception:
        messages.error(request, "Enter a valid amount to pay.")
        return redirect("customer_portal:collect_payment")

    if amount <= 0:
        messages.error(request, "Amount must be greater than zero.")
        return redirect("customer_portal:collect_payment")

    latest_order = _latest_order_for_customer(customer)
    if latest_order and latest_order.order_number:
        payment_order_id = f"{latest_order.order_number}-DUE-{timezone.now().strftime('%H%M%S%f')}"[:64]
    else:
        payment_order_id = f"CPD{customer.id}{timezone.now().strftime('%Y%m%d%H%M%S%f')}"[:64]
    linked_bill = _latest_due_bill_for_customer(customer)
    # Gateway integration point - create CustomerPayment with gateway fields
    # payment_order_id = f"CPD-{customer.phone}-{timezone.now().strftime('%Y%m%d%H%M%S%f')[:10]}"
    # payment = CustomerPayment.objects.create(
    #     customer=customer,
    #     amount=amount,
    #     transaction_id=f"GATEWAY-{payment_order_id}",
    #     method="gateway",
    #     status="pending",
    #     payment_order_id=payment_order_id,
    # )
    messages.success(request, f"UPI Payment link ready for Rs. {amount}. Complete payment and note transaction ID.")
    return redirect("customer_portal:collect_payment")


# ======================================================
# LOGOUT
# ======================================================
@never_cache
def logout_user(request):
    storage = get_messages(request)
    for _ in storage:
        pass
    logout(request)
    return redirect('/')
