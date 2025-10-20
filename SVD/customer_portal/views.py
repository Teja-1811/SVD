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
    if request.method == 'POST':
        # Handle order submission
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            delivery_date = data.get('delivery_date')
            additional_notes = data.get('additional_notes', '')
            delivery_address = data.get('delivery_address', '')
            phone = data.get('phone', '')

            if not items:
                return JsonResponse({'success': False, 'message': 'No items in order.'})

            # Generate order number
            order_number = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}"

            # Create order
            order = CustomerOrder.objects.create(
                order_number=order_number,
                customer=request.user,
                delivery_date=delivery_date if delivery_date else None,
                additional_notes=additional_notes,
                delivery_address=delivery_address,
                phone=phone,
                created_by=request.user
            )

            total_amount = 0
            for item_data in items:
                item_id = item_data.get('item_id')
                quantity = item_data.get('quantity')
                price = item_data.get('price')

                item = get_object_or_404(Item, id=item_id)
                total = quantity * price

                CustomerOrderItem.objects.create(
                    order=order,
                    item=item,
                    requested_quantity=quantity,
                    requested_price=price,
                    requested_total=total
                )
                total_amount += total

            order.total_amount = total_amount
            order.save()

            return JsonResponse({'success': True, 'message': 'Order placed successfully!', 'order_number': order_number})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    # GET request - show order form
    items = Item.objects.all()
    today = timezone.now().date()
    customer_orders = CustomerOrder.objects.filter(customer=request.user, order_date=today).order_by('-order_date')

    # Group items by company and then by category
    items_by_company = {}
    for item in items:
        company = item.company or 'Other'
        category = item.category or 'Other'
        if company not in items_by_company:
            items_by_company[company] = {}
        if category not in items_by_company[company]:
            items_by_company[company][category] = []
        items_by_company[company][category].append(item)

    # Prepare items data for JavaScript
    items_data = {}
    for company, categories in items_by_company.items():
        items_data[company] = {}
        for category, category_items in categories.items():
            items_data[company][category] = [
                {
                    'id': item.id,
                    'name': item.name,
                    'selling_price': float(item.selling_price)
                }
                for item in category_items
            ]

    context = {
        'items_by_company': items_by_company,
        'customer_orders': customer_orders,
        'items_data_json': json.dumps(items_data)
    }
    return render(request, 'customer_portal/customer_orders_dashboard.html', context)

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

    context = {
        'bills': bills,
        'selected_date': selected_month,
        'current_year': year,
        'current_month': month
    }
    return render(request, 'customer_portal/reports_dashboard.html', context)

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
def logout_view(request):
    # Clear the session completely
    request.session.flush()

    # Logout the user
    logout(request)

    # Add a success message
    messages.success(request, 'You have been successfully logged out.')

    # Create response with cache control headers
    response = redirect('index')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    # Redirect to index page
    return response
