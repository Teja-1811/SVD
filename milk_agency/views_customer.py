from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from .models import Customer, Bill, CustomerPayment
from django.utils import timezone
from django.db import transaction
import uuid


# -------------------------------------------------------
# ADD / EDIT CUSTOMER
# -------------------------------------------------------
@login_required
def add_customer(request, customer_id=None):
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
            customer.user_type = 'retailer'
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
                user_type='retailer',
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
def customer_data(request):
    area_filter = request.GET.get('area', '').strip()
    id_filter = request.GET.get('id', '').strip()

    customers = Customer.objects.filter(user_type="retailer").order_by('id')

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


# -------------------------------------------------------
# UPDATE CUSTOMER BALANCE (SAFE + ATOMIC)
# -------------------------------------------------------
@login_required
def update_customer_balance(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == 'POST':
        balance_str = request.POST.get('balance', '0')

        try:
            amount = Decimal(balance_str)

            with transaction.atomic():
                current_month = timezone.now().month
                current_year = timezone.now().year

                recent_bill = Bill.objects.filter(
                    customer=customer,
                    invoice_date__year=current_year,
                    invoice_date__month=current_month
                ).order_by('-id').first()

                if recent_bill and amount > 0:
                    recent_bill.last_paid += amount
                    recent_bill.save()

                if amount > 0:
                    CustomerPayment.objects.create(
                        customer=customer,
                        amount=amount,
                        transaction_id=f"PAY-{uuid.uuid4().hex[:10].upper()}",
                        method='Cash',
                        status='SUCCESS',
                    )

                # 🔥 Recalculate due instead of blindly subtracting
                customer.due = customer.get_actual_due()
                customer.save()

            msg = f'Balance updated for {customer.name}'

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': msg,
                    'new_balance': float(customer.due)
                })

            messages.success(request, msg)

        except Exception as e:
            messages.error(request, str(e))

    return redirect('milk_agency:customer_data')


# -------------------------------------------------------
# FREEZE / UNFREEZE CUSTOMER
# -------------------------------------------------------
@login_required
def freeze_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == 'POST':
        customer.frozen = not customer.frozen
        customer.save()

        status = "frozen" if customer.frozen else "unfrozen"
        messages.success(request, f'Customer {customer.name} has been {status}')

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'frozen': customer.frozen,
                'message': f'Customer {customer.name} has been {status}'
            })

    return redirect('milk_agency:customer_data')
