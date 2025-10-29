from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models.functions import TruncMonth
from django.db.models import Count, Sum
import json
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

    # Chart data for today's sales trends
    today = timezone.now().date()
    sales_today = Sale.objects.filter(invoice_date=today)

    # Since invoice_date is DateField, we can't group by hour
    # Show today's total sales data as a single data point
    today_sales_count = sales_today.count()
    today_revenue = sales_today.aggregate(total=Sum('total_amount'))['total'] or 0
    today_profit = sales_today.aggregate(total=Sum('profit'))['total'] or 0

    # Create chart data with single point for today
    sales_labels = ['Today']
    sales_counts = [today_sales_count]
    revenue_data = [float(today_revenue)]
    profit_data = [float(today_profit)]

    # Top selling products
    top_products = SaleItem.objects.values('product__name').annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total_amount')
    ).order_by('-total_quantity')[:10]

    product_labels = [item['product__name'] for item in top_products]
    product_quantities = [item['total_quantity'] for item in top_products]
    product_revenues = [float(item['total_revenue'] or 0) for item in top_products]

    # Revenue by category
    category_revenue = Product.objects.values('category__name').annotate(
        revenue=Sum('selling_price') * Sum('stock_quantity')  # Approximate revenue potential
    ).order_by('-revenue')[:5]

    category_labels = [item['category__name'] for item in category_revenue]
    category_data = [float(item['revenue'] or 0) for item in category_revenue]

    context = {
        'total_products': total_products,
        'total_categories': total_categories,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'low_stock_products': low_stock_products,
        'sales_labels': json.dumps(sales_labels),
        'sales_counts': json.dumps(sales_counts),
        'revenue_data': json.dumps(revenue_data),
        'profit_data': json.dumps(profit_data),
        'product_labels': json.dumps(product_labels),
        'product_quantities': json.dumps(product_quantities),
        'product_revenues': json.dumps(product_revenues),
        'category_labels': json.dumps(category_labels),
        'category_data': json.dumps(category_data),
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
def customer_list(request):
    customers = Customer.objects.all()
    return render(request, 'general_store/customer_list.html', {'customers': customers})

@login_required
def add_customer(request):
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

@login_required
def sales_list(request):
    sales = Sale.objects.select_related('customer').all()
    return render(request, 'general_store/sales_list.html', {'sales': sales})

@login_required
def add_sale(request):
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

@login_required
def view_sale(request, pk):
    sale = get_object_or_404(Sale.objects.select_related('customer'), pk=pk)
    sale_items = SaleItem.objects.select_related('product').filter(sale=sale)
    return render(request, 'general_store/view_sale.html', {
        'sale': sale,
        'sale_items': sale_items
    })

@login_required
def edit_sale(request, pk):
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
def sales_trends(request):
    """
    Sales trends dashboard with filtering options
    """
    from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
    from django.db.models import Count, Sum
    import json
    from datetime import timedelta

    # Get filter parameters
    filter_type = request.GET.get('filter', 'month')  # today, week, month, year
    category_id = request.GET.get('category', '')  # category filter

    now = timezone.now()
    current_period_start = None
    previous_period_start = None
    previous_period_end = None
    trunc_func = None

    if filter_type == 'today':
        current_period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        previous_period_start = current_period_start - timedelta(days=1)
        previous_period_end = current_period_start - timedelta(seconds=1)
        trunc_func = TruncDay
    elif filter_type == 'week':
        current_period_start = now - timedelta(days=now.weekday())
        current_period_start = current_period_start.replace(hour=0, minute=0, second=0, microsecond=0)
        previous_period_start = current_period_start - timedelta(days=7)
        previous_period_end = current_period_start - timedelta(seconds=1)
        trunc_func = TruncWeek
    elif filter_type == 'year':
        current_period_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_period_start = current_period_start.replace(year=current_period_start.year - 1)
        previous_period_end = current_period_start - timedelta(seconds=1)
        trunc_func = TruncYear
    else:  # month (default)
        current_period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_period_start = (current_period_start - timedelta(days=1)).replace(day=1)
        previous_period_end = current_period_start - timedelta(seconds=1)
        trunc_func = TruncMonth

    # Base queryset for current period
    current_sales_base = Sale.objects.filter(invoice_date__gte=current_period_start)
    if category_id:
        current_sales_base = current_sales_base.filter(items__product__category_id=category_id).distinct()

    # Current period data
    current_sales = current_sales_base
    current_total_sales = current_sales.count()
    current_total_revenue = current_sales.aggregate(total=Sum('total_amount'))['total'] or 0
    current_total_profit = current_sales.aggregate(total=Sum('profit'))['total'] or 0

    # Previous period data
    previous_sales_base = Sale.objects.filter(
        invoice_date__gte=previous_period_start,
        invoice_date__lte=previous_period_end
    )
    if category_id:
        previous_sales_base = previous_sales_base.filter(items__product__category_id=category_id).distinct()

    previous_sales = previous_sales_base
    previous_total_sales = previous_sales.count()
    previous_total_revenue = previous_sales.aggregate(total=Sum('total_amount'))['total'] or 0
    previous_total_profit = previous_sales.aggregate(total=Sum('profit'))['total'] or 0

    # Calculate percentage changes
    sales_change = ((current_total_sales - previous_total_sales) / previous_total_sales * 100) if previous_total_sales > 0 else 0
    revenue_change = ((current_total_revenue - previous_total_revenue) / previous_total_revenue * 100) if previous_total_revenue > 0 else 0
    profit_change = ((current_total_profit - previous_total_profit) / previous_total_profit * 100) if previous_total_profit > 0 else 0

    # Chart data for current period
    sales_by_period = current_sales_base.annotate(
        period=trunc_func('invoice_date')
    ).values('period').annotate(
        count=Count('id'),
        revenue=Sum('total_amount'),
        profit=Sum('profit')
    ).order_by('period')

    labels = []
    sales_counts = []
    revenue_data = []
    profit_data = []

    for item in sales_by_period:
        if filter_type == 'today':
            labels.append(item['period'].strftime('%H:%M'))
        elif filter_type == 'week':
            labels.append(item['period'].strftime('%a'))
        elif filter_type == 'year':
            labels.append(item['period'].strftime('%b'))
        else:  # month
            labels.append(item['period'].strftime('%d'))

        sales_counts.append(item['count'])
        revenue_data.append(float(item['revenue'] or 0))
        profit_data.append(float(item['profit'] or 0))

    # Top products for current period
    top_products_base = SaleItem.objects.filter(
        sale__invoice_date__gte=current_period_start
    )
    if category_id:
        top_products_base = top_products_base.filter(product__category_id=category_id)

    top_products = top_products_base.values('product__name').annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total_amount')
    ).order_by('-total_quantity')[:10]

    product_labels = [item['product__name'] for item in top_products]
    product_quantities = [item['total_quantity'] for item in top_products]
    product_revenues = [float(item['total_revenue'] or 0) for item in top_products]

    # Category-wise analytics for current period
    category_analytics_base = SaleItem.objects.filter(
        sale__invoice_date__gte=current_period_start
    )
    if category_id:
        category_analytics_base = category_analytics_base.filter(product__category_id=category_id)

    category_analytics = category_analytics_base.values('product__category__name').annotate(
        total_sales=Count('sale', distinct=True),
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total_amount'),
        total_profit=Sum('sale__profit')
    ).order_by('-total_revenue')

    # Convert to list and add avg_sale_value
    category_analytics = list(category_analytics)
    for item in category_analytics:
        item['avg_sale_value'] = item['total_revenue'] / item['total_sales'] if item['total_sales'] else 0

    # Get top and bottom performing categories
    top_category = category_analytics[0] if category_analytics else None
    bottom_category = category_analytics[-1] if category_analytics else None

    # Category summary
    category_summary = {
        'total_categories': len(category_analytics),
        'top_category': top_category['product__category__name'] if top_category else 'N/A',
        'top_category_revenue': float(top_category['total_revenue'] or 0) if top_category else 0,
        'bottom_category': bottom_category['product__category__name'] if bottom_category else 'N/A',
        'bottom_category_revenue': float(bottom_category['total_revenue'] or 0) if bottom_category else 0,
    }

    # Safe access for template
    top_category_sales = top_category['total_sales'] if top_category else 0
    top_category_profit = float(top_category['total_profit'] or 0) if top_category else 0
    bottom_category_sales = bottom_category['total_sales'] if bottom_category else 0
    bottom_category_profit = float(bottom_category['total_profit'] or 0) if bottom_category else 0

    # Get all categories for filter dropdown
    categories = Category.objects.all()

    context = {
        'filter_type': filter_type,
        'category_id': category_id,
        'categories': categories,
        'current_total_sales': current_total_sales,
        'current_total_revenue': current_total_revenue,
        'current_total_profit': current_total_profit,
        'previous_total_sales': previous_total_sales,
        'previous_total_revenue': previous_total_revenue,
        'previous_total_profit': previous_total_profit,
        'sales_change': sales_change,
        'revenue_change': revenue_change,
        'profit_change': profit_change,
        'labels': json.dumps(labels),
        'sales_counts': json.dumps(sales_counts),
        'revenue_data': json.dumps(revenue_data),
        'profit_data': json.dumps(profit_data),
        'product_labels': json.dumps(product_labels),
        'product_quantities': json.dumps(product_quantities),
        'product_revenues': json.dumps(product_revenues),
        'category_summary': category_summary,
        'category_analytics': list(category_analytics),
    }
    return render(request, 'general_store/sales_trends.html', context)

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
