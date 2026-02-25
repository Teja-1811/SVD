from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Customer, UserPayment
from django.utils import timezone
from django.db import transaction
import uuid


# -------------------------------------------------------
# ADD / EDIT USER
# -------------------------------------------------------
@login_required
def add_user(request, customer_id=None):
    customer = get_object_or_404(Customer, id=customer_id) if customer_id else None

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
        is_commissioned = request.POST.get('is_commissioned') == 'on'

        if customer:
            customer.name = name
            customer.shop_name = shop_name
            customer.retailer_id = retailer_id
            customer.flat_number = flat_number
            customer.area = area
            customer.phone = phone
            customer.pin_code = pin_code
            customer.user_type = 'user'
            customer.city = city
            customer.state = state
            customer.is_commissioned = is_commissioned
            customer.save()
            messages.success(request, f'Customer {customer.name} updated successfully!')
        else:
            customer_code = str(Customer.objects.count()+1).zfill(3)
            customer = Customer.objects.create(
                name=name,
                shop_name=shop_name,
                retailer_id=f"SVD-{city}-{customer_code}",
                flat_number=flat_number,
                area=area,
                phone=phone,
                pin_code=pin_code,
                user_type='user',
                city=city,
                state=state,
                is_commissioned=is_commissioned,
                password=phone
            )
            messages.success(request, f'Customer {customer.name} added successfully!')

        return redirect('milk_agency:customer_data')

    return render(request, 'milk_agency/customer/add_customer.html', {
        'customer': customer,
        'is_edit': customer is not None
    })


# -------------------------------------------------------
# CUSTOMER LIST + FILTERS
# -------------------------------------------------------
@login_required
def user_data(request):
    area_filter = request.GET.get('area', '').strip()
    id_filter = request.GET.get('id', '').strip()

    customers = Customer.objects.filter(user_type="user").order_by('id')

    if area_filter and area_filter != "All":
        customers = customers.filter(area__icontains=area_filter)

    if id_filter and id_filter != "All":
        if id_filter.isdigit():
            customers = customers.filter(id=id_filter)
        else:
            customers = customers.filter(name__icontains=id_filter)

    # SAFE: show real due
    for c in customers:
        c.total_balance = c.get_actual_due()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'customers': [{
                'id': c.id,
                'name': c.name,
                'shop_name': c.shop_name or '-',
                'retailer_id': c.retailer_id or '-',
                'phone': c.phone,
                'balance': float(c.get_actual_due()),
                'frozen': c.frozen,
            } for c in customers]
        })

    areas = Customer.objects.exclude(area__isnull=True).exclude(area='').values_list('area', flat=True).distinct()
    names = list(Customer.objects.values_list('id', 'name').order_by('name'))

    return render(request, 'milk_agency/customer/customer_data.html', {
        'customers': customers,
        'areas': areas,
        'names': names,
        'selected_area': area_filter,
        'selected_id': id_filter,
    })
