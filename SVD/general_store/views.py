from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from .models import Category, Product, Sale, SaleItem, Customer
from decimal import Decimal

@login_required
def home(request):
    # Dashboard
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_sales = Sale.objects.count()
    total_revenue = Sale.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    low_stock_products = Product.objects.filter(stock_quantity__lt=10)
    context = {
        'total_products': total_products,
        'total_categories': total_categories,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'low_stock_products': low_stock_products,
    }
    return render(request, 'general_store/home.html', context)

@login_required
def product_list(request):
    products = Product.objects.select_related('category').all()
    return render(request, 'general_store/product_list.html', {'products': products})

@login_required
def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        buying_price = request.POST.get('buying_price')
        selling_price = request.POST.get('selling_price')
        mrp = request.POST.get('mrp')
        stock_quantity = request.POST.get('stock_quantity')
        
        category = get_object_or_404(Category, id=category_id)
        Product.objects.create(
            name=name,
            category=category,
            buying_price=buying_price,
            selling_price=selling_price,
            mrp=mrp,
            stock_quantity=stock_quantity
        )
        messages.success(request, 'Product added successfully.')
        return redirect('general_store:product_list')
    
    categories = Category.objects.all()
    return render(request, 'general_store/add_product.html', {'categories': categories})

@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.name = request.POST.get('name')
        category_id = request.POST.get('category')
        product.buying_price = request.POST.get('buying_price')
        product.selling_price = request.POST.get('selling_price')
        product.mrp = request.POST.get('mrp')
        product.stock_quantity = request.POST.get('stock_quantity')
        product.category = get_object_or_404(Category, id=category_id)
        product.save()
        messages.success(request, 'Product updated successfully.')
        return redirect('general_store:product_list')
    
    categories = Category.objects.all()
    return render(request, 'general_store/add_product.html', {'product': product, 'categories': categories})

@login_required
def sales_list(request):
    sales = Sale.objects.select_related('customer').all()
    return render(request, 'general_store/sales_list.html', {'sales': sales})

@login_required
def customer_list(request):
    customers = Customer.objects.all().order_by('name')
    return render(request, 'general_store/customer_list.html', {'customers': customers})

@login_required
def add_customer(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address', '')
        balance = request.POST.get('balance', 0)

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
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer.name = request.POST.get('name')
        customer.phone = request.POST.get('phone')
        customer.address = request.POST.get('address', '')
        customer.balance = request.POST.get('balance', 0)
        customer.save()
        messages.success(request, 'Customer updated successfully.')
        return redirect('general_store:customer_list')

    return render(request, 'general_store/add_customer.html', {'customer': customer})

@login_required
def add_sale(request):
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        bill_date = request.POST.get('bill_date')
        products = request.POST.getlist('products')
        quantities = request.POST.getlist('quantities')
        discounts = request.POST.getlist('discounts')

        customer = get_object_or_404(Customer, id=customer_id)

        with transaction.atomic():
            # Generate invoice number
            invoice_number = f"GS-{timezone.now().strftime('%Y%m%d')}-{Sale.objects.count() + 1}"

            sale = Sale.objects.create(
                customer=customer,
                invoice_number=invoice_number,
                invoice_date=bill_date,
                total_amount=0,
                due_amount=0
            )

            total_amount = 0
            profit = 0

            for i, product_id in enumerate(products):
                if product_id and quantities[i]:
                    product = get_object_or_404(Product, id=product_id)
                    quantity = int(quantities[i])
                    discount = Decimal(discounts[i]) if discounts[i] else 0

                    price_per_unit = product.selling_price
                    item_total = (price_per_unit * quantity) - discount

                    SaleItem.objects.create(
                        sale=sale,
                        product=product,
                        price_per_unit=price_per_unit,
                        discount=discount,
                        quantity=quantity,
                        total_amount=item_total
                    )

                    total_amount += item_total
                    profit += (price_per_unit - product.buying_price) * quantity

                    # Update stock
                    product.stock_quantity -= quantity
                    product.save()

            sale.total_amount = total_amount
            sale.profit = profit
            sale.due_amount = total_amount
            sale.save()

        messages.success(request, 'Sale added successfully.')
        return redirect('general_store:sales_list')

    customers = Customer.objects.all()
    products = Product.objects.all()
    today = timezone.now().date()
    return render(request, 'general_store/add_sale.html', {
        'customers': customers,
        'products': products,
        'today': today
    })
