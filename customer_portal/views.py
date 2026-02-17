from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.utils import timezone
from datetime import time
from decimal import Decimal, InvalidOperation
import json

from milk_agency.models import Customer, Item, Bill, CustomerPayment
from milk_agency.payment_gateway import (
    generate_upi_link,
    generate_upi_qr,
    generate_upi_payment_link,
    generate_transaction_id
)

from .models import CustomerOrder, CustomerOrderItem


# ======================================================
# LOGIN
# ======================================================
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return redirect('customer_portal:login')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if isinstance(user, Customer):
                login(request, user, backend='customer_portal.authentication.CustomerBackend')
                if user.is_staff:
                    return redirect('milk_agency:home')
                else:
                    return redirect('customer_portal:home')
            else:
                login(request, user)
                return redirect('milk_agency:home')
        else:
            messages.error(request, 'Invalid username or password.')
            return redirect('/')

    return render(request, 'index.html')


# ======================================================
# HOME
# ======================================================
@login_required
@never_cache
def home(request):
    return render(request, 'customer_portal/home.html')


# ======================================================
# CUSTOMER ORDERS DASHBOARD
# ======================================================
@never_cache
@login_required
def customer_orders_dashboard(request):

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            items = data.get('items', [])

            if not items:
                return JsonResponse({'success': False, 'message': 'No items selected'})

            order_number = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}"

            order = CustomerOrder.objects.create(
                order_number=order_number,
                customer=request.user,
                created_by=request.user
            )

            total_amount = 0
            for i in items:
                item = get_object_or_404(Item, id=i["item_id"])
                qty = i["quantity"]
                price = i["price"]
                line_total = qty * price

                CustomerOrderItem.objects.create(
                    order=order,
                    item=item,
                    requested_quantity=qty,
                    requested_price=price,
                    requested_total=line_total
                )

                total_amount += line_total

            order.total_amount = total_amount
            order.save()

            return JsonResponse({'success': True, 'order_number': order_number})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    items = Item.objects.select_related("company").filter(company__name__iexact="Dodla")

    for item in items:
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

        start_time = time(12, 0)  # 12 PM
        end_time = time(5, 0)     # 5 AM

        if end_time <= current_time < start_time:
            return JsonResponse({
                "success": False,
                "message": "Orders allowed only between 12:00 PM and 5:00 AM"
            }, status=403)

        data = json.loads(request.body)
        items = data.get("items", [])

        if not items:
            return JsonResponse({"success": False, "message": "No items selected"}, status=400)

        order_number = f"ORD-{now.strftime('%Y%m%d%H%M%S')}"
        customer = request.user

        delivery_time = now.replace(hour=17, minute=0, second=0, microsecond=0)

        order = CustomerOrder.objects.create(
            order_number=order_number,
            customer=customer,
            created_by=customer,
            delivery_time=delivery_time
        )

        total_amount = 0

        for i in items:
            item = get_object_or_404(Item, id=i["item_id"])
            qty = int(i["quantity"])

            if qty <= 0:
                continue

            price = float(item.selling_price)
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
        order.approved_total_amount = total_amount
        order.save()

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
    order = CustomerOrder.objects.filter(customer=request.user).order_by('-order_date').first()

    bill = None
    if order:
        bill = Bill.objects.filter(
            customer=order.customer,
            total_amount=order.approved_total_amount
        ).order_by('-invoice_date').first()

    return render(request, "customer_portal/last_order_details.html", {
        "order": order,
        "bill": bill
    })


# ======================================================
# BILL DETAILS
# ======================================================
@never_cache
@login_required
def bill_details(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id, customer=request.user)
    bill_items = bill.items.all().select_related('item')

    return render(request, 'customer_portal/bill_details.html', {
        'bill': bill,
        'bill_items': bill_items,
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
# COLLECT PAYMENT (USE ACTUAL DUE)
# ======================================================
@login_required
def collect_payment(request):
    customer = request.user

    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount"))
        except (InvalidOperation, TypeError):
            messages.error(request, "Invalid amount")
            return redirect("customer_portal:collect_payment")

        if amount <= 0:
            messages.error(request, "Invalid payment amount")
            return redirect("customer_portal:collect_payment")

        txn_id = generate_transaction_id()

        upi_link = generate_upi_link(amount=amount, note=f"Due Payment - {customer.name}", txn_id=txn_id)
        qr_base64 = generate_upi_qr(amount=amount, note=f"Due Payment - {customer.name}", txn_id=txn_id)
        payment_link = generate_upi_payment_link(amount=amount, note=f"Due Payment - {customer.name}")

        CustomerPayment.objects.create(
            customer=customer,
            amount=amount,
            transaction_id=txn_id,
            method="UPI",
            status="PENDING"
        )

        return render(request, "customer_portal/collect_payment.html", {
            "due": customer.get_actual_due(),
            "amount": amount,
            "upi_link": upi_link,
            "qr_base64": qr_base64,
            "payment_link": payment_link,
            "txn_id": txn_id
        })

    return render(request, "customer_portal/collect_payment.html", {
        "due": customer.get_actual_due()
    })


# ======================================================
# LOGOUT
# ======================================================
@never_cache
def logout_user(request):
    logout(request)
    return redirect('/')
