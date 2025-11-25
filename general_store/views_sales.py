from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from .models import Product, Sale, SaleItem, Customer


@login_required
def sales_list(request):
    """
    Display list of all sales
    """
    sales = Sale.objects.select_related('customer').all()
    return render(request, 'general_store/sales_list.html', {'sales': sales})


@login_required
def add_sale(request):
    """
    Create a new sale transaction
    """
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        bill_date = request.POST.get('bill_date')
        products = request.POST.getlist('products')
        quantities = request.POST.getlist('quantities')
        discounts = request.POST.getlist('discounts')

        customer = None
        if customer_id:
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

                    price_per_unit = product.mrp
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


@login_required
def view_sale(request, pk):
    """
    View details of a specific sale
    """
    sale = get_object_or_404(Sale.objects.select_related('customer'), pk=pk)
    sale_items = SaleItem.objects.select_related('product').filter(sale=sale)
    return render(request, 'general_store/view_sale.html', {
        'sale': sale,
        'sale_items': sale_items
    })


@login_required
def edit_sale(request, pk):
    """
    Edit an existing sale
    """
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        bill_date = request.POST.get('bill_date')
        products = request.POST.getlist('products')
        quantities = request.POST.getlist('quantities')
        discounts = request.POST.getlist('discounts')

        customer = None
        if customer_id:
            customer = get_object_or_404(Customer, id=customer_id)

        with transaction.atomic():
            # Restore stock for existing items
            for item in SaleItem.objects.filter(sale=sale):
                item.product.stock_quantity += item.quantity
                item.product.save()

            # Delete existing sale items
            SaleItem.objects.filter(sale=sale).delete()

            # Update sale details
            sale.customer = customer
            sale.invoice_date = bill_date
            sale.total_amount = 0
            sale.due_amount = 0
            sale.profit = 0

            total_amount = 0
            profit = 0

            for i, product_id in enumerate(products):
                if product_id and quantities[i]:
                    product = get_object_or_404(Product, id=product_id)
                    quantity = int(quantities[i])
                    discount = Decimal(discounts[i]) if discounts[i] else 0

                    price_per_unit = product.mrp
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

        messages.success(request, 'Sale updated successfully.')
        return redirect('general_store:sales_list')

    sale_items = SaleItem.objects.select_related('product').filter(sale=sale)
    customers = Customer.objects.all()
    products = Product.objects.all()
    return render(request, 'general_store/edit_sale.html', {
        'sale': sale,
        'sale_items': sale_items,
        'customers': customers,
        'products': products
    })


@login_required
def delete_sale(request, pk):
    """
    Delete a sale and restore stock
    """
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            # Restore stock
            for item in SaleItem.objects.filter(sale=sale):
                item.product.stock_quantity += item.quantity
                item.product.save()

            sale.delete()
        messages.success(request, 'Sale deleted successfully.')
        return redirect('general_store:sales_list')

    return render(request, 'general_store/delete_sale.html', {'sale': sale})


@login_required
def generate_sale_pdf(request, pk):
    """
    Generate sale PDF and return as download
    """
    sale = get_object_or_404(Sale, pk=pk)
    from .pdf_utils import PDFGenerator
    pdf_generator = PDFGenerator()
    response = pdf_generator.generate_and_return_pdf(sale, request)
    return response


@login_required
def anonymous_bills_list(request):
    """
    List all sales without customers (anonymous bills)
    """
    anonymous_sales = Sale.objects.filter(customer__isnull=True).select_related('customer').all()
    return render(request, 'general_store/anonymous_bills_list.html', {'sales': anonymous_sales})
