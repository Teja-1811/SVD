from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Customer
from .views_customer import save_customer_form


# -------------------------------------------------------
# ADD / EDIT USER
# -------------------------------------------------------
@login_required
def add_user(request, customer_id=None):
    return save_customer_form(request, customer_id=customer_id, default_user_type="user")


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

    areas = Customer.objects.filter(user_type="user").exclude(area__isnull=True).exclude(area='').values_list('area', flat=True).distinct()
    names = list(Customer.objects.filter(user_type="user").values_list('id', 'name').order_by('name'))

    return render(request, 'milk_agency/customer/customer_data.html', {
        'customers': customers,
        'areas': areas,
        'names': names,
        'selected_area': area_filter,
        'selected_id': id_filter,
        'selected_type': 'user',
    })
