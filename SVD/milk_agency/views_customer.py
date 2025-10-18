from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from .models import Customer, Bill
from django.utils.timezone import now

@login_required
def add_customer(request, customer_id=None):
    if customer_id:
        customer = get_object_or_404(Customer, id=customer_id)
    else:
        customer = None

    if request.method == 'POST':
        name = request.POST.get('party_name')
        shop_name = request.POST.get('shop_name')
        retailer_id = request.POST.get('retailer_id')
        flat_number = request.POST.get('flat_number')
        area = request.POST.get('area')
        phone = request.POST.get('phone')
        pin_code = request.POST.get('pin_code')
        city = request.POST.get('city')
        state = request.POST.get('state')
        # Removed milk_commission and curd_commission from POST handling
        if customer and customer.city != city:
            retailer_id = "SVD-"+city+retailer_id[-4:]
        
        if customer:
            # Update existing customer
            customer.name = name
            customer.shop_name = shop_name
            customer.retailer_id = retailer_id
            customer.flat_number = flat_number
            customer.area = area
            customer.phone = phone
            customer.pin_code = pin_code
            customer.city = city
            customer.state = state
            customer.password=phone
            customer.save()
            messages.success(request, f'Customer {customer.name} updated successfully!')
        else:
            customer_code = str(Customer.objects.count()+1)
            if len(customer_code) == 1:
                customer_code ="-00"+customer_code
            elif len(customer_code) == 2:
                customer_code = "-0"+customer_code
            else:
                customer_code = "-"+customer_code
            # Create new customer
            customer = Customer.objects.create(
                name=name,
                shop_name=shop_name,
                retailer_id="SVD-"+city+customer_code,
                flat_number=flat_number,
                area=area,
                phone=phone,
                pin_code=pin_code,
                city=city,
                state=state,
                password=phone  # Set phone number as default password
            )
            messages.success(request, f'Customer {customer.name} added successfully!')

        return redirect('milk_agency:customer_data')

    context = {
        'customer': customer,
        'is_edit': customer is not None
    }
    return render(request, 'milk_agency/customer/add_customer.html', context)

@login_required
def customer_data(request):
    # Get filter parameters
    area_filter = request.GET.get('area')
    name_filter = request.GET.get('name')

    customers = Customer.objects.all().order_by('name')

    # Apply filters
    if area_filter:
        customers = customers.filter(area__icontains=area_filter)
    if name_filter:
        customers = customers.filter(name__icontains=name_filter)

    # Calculate total balance for each customer
    for customer in customers:
        customer.total_balance = customer.bills.aggregate(
            total=Sum('op_due_amount')
        )['total'] or 0

    # Check if AJAX request
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        customer_data = []
        for customer in customers:
            customer_data.append({
                'id': customer.id,
                'name': customer.name,
                'shop_name': customer.shop_name or '-',
                'retailer_id': customer.retailer_id or '-',
                'address': f"{customer.flat_number}, {customer.area or ''} {customer.city or ''} {customer.state or ''}-{customer.pin_code or ''}".strip(', '),
                'phone': customer.phone,
                # Removed commission fields
                'balance': customer.due or 0,
                'frozen': customer.frozen,
            })
        return JsonResponse({'customers': customer_data})

    # Get data for filter dropdowns
    areas = Customer.objects.exclude(area__isnull=True).exclude(area='').values_list('area', flat=True).distinct().order_by('area')
    names = Customer.objects.values_list('name', flat=True).distinct().order_by('name')
    active_customers_count = Customer.objects.filter(frozen=False).count()
    inactive_customers_count = Customer.objects.filter(frozen=True).count()

    context = {
        'customers': customers,
        'areas': areas,
        'names': names,
        'selected_area': area_filter,
        'selected_name': name_filter,
        'active_customers_count': active_customers_count,
        'inactive_customers_count': inactive_customers_count,
    }
    return render(request, 'milk_agency/customer/customer_data.html', context)

@login_required
def update_customer_balance(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == 'POST':
        balance = request.POST.get('balance', 0)
        try:
            balance_decimal = Decimal(balance)
            # No recent bill found, update only customer due and last_paid_balance
            customer.due -= balance_decimal
            customer.last_paid_balance = balance_decimal
            customer.save()
            messages.success(request, f'Balance updated for {customer.name} without a recent bill')
        except ValueError:
            messages.error(request, 'Invalid balance value')

    return redirect('milk_agency:customer_data')

@login_required
def freeze_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == 'POST':
        customer.frozen = not customer.frozen
        customer.save()
        status = "frozen" if customer.frozen else "unfrozen"
        messages.success(request, f'Customer {customer.name} has been {status}')

        # Check if AJAX request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'frozen': customer.frozen,
                'message': f'Customer {customer.name} has been {status}'
            })

    return redirect('milk_agency:customer_data')
