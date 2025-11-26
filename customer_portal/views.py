from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.utils import timezone
from milk_agency.models import Customer, Item, Bill
from .models import CustomerOrder, CustomerOrderItem
import json

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return redirect('customer_portal:login')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # If it's a Customer, specify backend explicitly
            if isinstance(user, Customer):
                login(request, user, backend='customer_portal.authentication.CustomerBackend')
                # Check if user is admin (staff) or regular customer
                if user.is_staff:
                    return redirect('milk_agency:home')
                else:
                    return redirect('customer_portal:home')

            else:
                # Default Django User (admin/staff)
                login(request, user)
                return redirect('milk_agency:home')
        else:
            messages.error(request, 'Invalid username or password.')
            return redirect('/')

    return render(request, 'index.html')
    
@login_required
@never_cache
def home(request):
    # Customer home page
    return render(request, 'customer_portal/home.html')

@never_cache
@login_required
def customer_orders_dashboard(request):

    # ---------- POST: SAVE ORDER ----------
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

    # ---------- GET: RENDER ORDER PAGE ----------
    items = Item.objects.select_related("company").all()

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

    # ---------- CLEAN GROUPING STRUCTURE ----------
    # items_by_company = {
    #     "Dodla": {
    #         "Milk": [items],
    #         "Curd": [items]
    #     }
    # }

    items_by_company = {}

    for item in items:
        company = item.company.name if item.company else "Other"
        category = item.category if item.category else "Other"

        if company not in items_by_company:
            items_by_company[company] = {}

        if category not in items_by_company[company]:
            items_by_company[company][category] = []

        items_by_company[company][category].append(item)

        # Last order for status tracking
    last_order = CustomerOrder.objects.filter(
        customer=request.user
    ).order_by('-order_date').first()

    return render(request, 'customer_portal/customer_orders_dashboard.html', {
        'items_by_company': items_by_company,
        'customer_orders': customer_orders,
        'last_order': last_order,
    })
    
@csrf_exempt
@login_required
def place_order(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"}, status=400)

    try:
        data = json.loads(request.body)
        items = data.get("items", [])

        if not items:
            return JsonResponse({"success": False, "message": "No items selected"}, status=400)

        # Generate order number
        order_number = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}"

        customer = request.user  # Your logged-in customer object

        # Create order
        order = CustomerOrder.objects.create(
            order_number=order_number,
            customer=customer,
            created_by=customer,
        )

        total_amount = 0

        for i in items:
            item = get_object_or_404(Item, id=i["item_id"])
            qty = int(i["quantity"])
            price = float(i["price"])
            line_total = qty * price

            # Create order item
            CustomerOrderItem.objects.create(
                order=order,
                item=item,
                requested_quantity=qty,
                requested_price=price,
                requested_total=line_total
            )

            total_amount += line_total

        # Update total amount
        order.total_amount = total_amount
        order.approved_total_amount = total_amount  # default
        order.save()

        return JsonResponse({
            "success": True,
            "order_number": order_number
        })

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

@never_cache
@login_required
def reports_dashboard(request):
    """Customer reports dashboard showing invoices/bills"""
    selected_month = request.GET.get('date', timezone.now().strftime('%Y-%m'))
    try:
        year, month = map(int, selected_month.split('-'))
    except (ValueError, AttributeError):
        year = timezone.now().year
        month = timezone.now().month

    # Get bills for the current customer, filtered by selected month (default current)
    bills = Bill.objects.filter(
        customer=request.user,
        invoice_date__year=year,
        invoice_date__month=month
    ).select_related('customer').order_by('-invoice_date')

    # Calculate total and average amounts
    total_amount = sum(bill.total_amount for bill in bills) if bills else 0
    average_amount = total_amount / len(bills) if bills else 0

    context = {
        'bills': bills,
        'selected_date': selected_month,
        'current_year': year,
        'current_month': month,
        'total_amount': total_amount,
        'average_amount': average_amount
    }
    return render(request, 'customer_portal/reports_dashboard.html', context)

@login_required
@never_cache
def last_order_details(request):
    order = CustomerOrder.objects.filter(customer=request.user).order_by('-order_date').first()
    bill = Bill.objects.filter(
            customer=order.customer,
            total_amount=order.approved_total_amount
        ).order_by('-invoice_date').first()

    return render(request, "customer_portal/last_order_details.html", {
        "order": order,
        'bill': bill
    })


@never_cache
@login_required
def bill_details(request, bill_id):
    """Display detailed bill information for the logged-in customer"""
    # Get the bill for the current customer only
    bill = get_object_or_404(Bill, id=bill_id, customer=request.user)

    # Get bill items using the correct related name 'items'
    bill_items = bill.items.all().select_related('item')

    context = {
        'bill': bill,
        'bill_items': bill_items,
    }
    return render(request, 'customer_portal/bill_details.html', context)

@never_cache
@login_required
def update_profile(request):
    if request.method == 'POST':
        # Update customer profile
        customer = request.user  # Assuming user is Customer instance
        customer.name = request.POST.get('name', customer.name)
        customer.phone = request.POST.get('phone', customer.phone)
        customer.shop_name = request.POST.get('shop_name', customer.shop_name)
        customer.area = request.POST.get('area', customer.area)
        customer.city = request.POST.get('city', customer.city)
        customer.state = request.POST.get('state', customer.state)
        customer.pin_code = request.POST.get('pin_code', customer.pin_code)
        customer.save()

        # Handle password change
        new_password = request.POST.get('new_password')
        if new_password:
            current_password = request.POST.get('current_password')
            confirm_password = request.POST.get('confirm_password')
            
            if not customer.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
                return redirect('customer_portal:update_profile')
            
            if new_password != confirm_password:
                messages.error(request, "New passwords don't match.")
                return redirect('customer_portal:update_profile')
            
            if len(new_password) < 8:
                messages.error(request, 'New password must be at least 8 characters.')
                return redirect('customer_portal:update_profile')
            
            customer.set_password(new_password)
            customer.save()
            messages.success(request, 'Password updated successfully!')

        messages.success(request, 'Profile updated successfully!')
        return redirect('customer_portal:home')
    else:
        # GET request - display form with current data
        customer = request.user
        context = {
            'customer': customer,
        }
        return render(request, 'customer_portal/update_profile.html', context)

@never_cache
def logout_user(request):
    logout(request)
    return redirect('/')