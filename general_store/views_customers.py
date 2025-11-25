from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Customer


@login_required
def customer_list(request):
    """
    Display list of all customers
    """
    customers = Customer.objects.all()
    return render(request, 'general_store/customer_list.html', {'customers': customers})


@login_required
def add_customer(request):
    """
    Add a new customer
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        balance = request.POST.get('balance')
        Customer.objects.create(
            name=name,
            phone=phone,
            address=address,
            balance=balance
        )
        messages.success(request, 'Customer added successfully.')
        return redirect('general_store:customer_list')
    return render(request, 'general_store/add_customer.html')


@login_required
def edit_customer(request, pk):
    """
    Edit an existing customer
    """
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer.name = request.POST.get('name')
        customer.phone = request.POST.get('phone')
        customer.address = request.POST.get('address')
        customer.balance = request.POST.get('balance')
        customer.save()
        messages.success(request, 'Customer updated successfully.')
        return redirect('general_store:customer_list')
    return render(request, 'general_store/add_customer.html', {'customer': customer})
