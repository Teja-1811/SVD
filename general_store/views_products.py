from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Category, Product


@login_required
def product_list(request):
    """
    Display list of all products with their details
    """
    products = Product.objects.select_related('category').all()
    return render(request, 'general_store/product_list.html', {'products': products})


@login_required
def add_product(request):
    """
    Add a new product to the inventory
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        buying_price = request.POST.get('buying_price')
        mrp = request.POST.get('mrp')
        stock_quantity = request.POST.get('stock_quantity')

        category = get_object_or_404(Category, id=category_id)
        Product.objects.create(
            name=name,
            category=category,
            buying_price=buying_price,
            mrp=mrp,
            stock_quantity=stock_quantity
        )
        messages.success(request, 'Product added successfully.')
        return redirect('general_store:product_list')

    categories = Category.objects.all()
    return render(request, 'general_store/add_product.html', {'categories': categories})


@login_required
def edit_product(request, pk):
    """
    Edit an existing product
    """
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.name = request.POST.get('name')
        category_id = request.POST.get('category')
        product.buying_price = request.POST.get('buying_price')
        product.mrp = request.POST.get('mrp')
        product.stock_quantity = request.POST.get('stock_quantity')
        product.category = get_object_or_404(Category, id=category_id)
        product.save()
        messages.success(request, 'Product updated successfully.')
        return redirect('general_store:product_list')

    categories = Category.objects.all()
    return render(request, 'general_store/add_product.html', {'product': product, 'categories': categories})
