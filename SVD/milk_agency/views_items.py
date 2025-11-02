from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Item

@login_required
def items_dashboard(request):
    from itertools import groupby
    from collections import OrderedDict

    company_filter = request.GET.get('company')
    if company_filter:
        items = Item.objects.filter(company=company_filter).order_by('category', 'name')
    else:
        items = Item.objects.all().order_by('category', 'name')

    # Calculate stock value and margin for each item
    for item in items:
        item.stock_value = item.stock_quantity * item.buying_price
        item.margin = item.selling_price - item.buying_price

    # Group items by category
    grouped_items = {}
    for category, group in groupby(items, key=lambda x: (x.category or 'others').lower()):
        grouped_items[category] = sorted(list(group), key=lambda x: x.name.lower())

    # Define custom order for categories
    category_order = ['milk', 'curd', 'buckets', 'panner', 'sweets', 'flavoured milk', 'ghee', 'others']
    ordered_grouped = OrderedDict()
    for cat in category_order:
        ordered_grouped[cat] = grouped_items.get(cat, [])

    # Check if there are any items at all
    total_items = sum(len(items) for items in ordered_grouped.values())

    context = {
        'grouped_items': ordered_grouped,
        'total_items': total_items,
        'company_filter': company_filter
    }
    return render(request, 'milk_agency/items/items_dashboard.html', context)

@login_required
def add_item(request, item_id=None):
    if item_id:
        item = get_object_or_404(Item, id=item_id)
    else:
        item = None

    if request.method == 'POST':
        code = request.POST.get('code')
        name = request.POST.get('name')
        company = request.POST.get('company')
        category = request.POST.get('category')
        buying_price = request.POST.get('buying_price', 0)
        selling_price = request.POST.get('selling_price', 0)
        mrp = request.POST.get('mrp', 0)
        stock_quantity = request.POST.get('stock_quantity', 0)
        pcs_count = request.POST.get('pcs_count', 1)
        image = request.FILES.get('image')
        try:
            buying_price = float(buying_price)
            selling_price = float(selling_price)
            mrp = float(mrp)
            stock_quantity = int(stock_quantity)
            pcs_count = int(pcs_count)
        except ValueError:
            messages.error(request, 'Invalid numeric values')
            return redirect('milk_agency:items_dashboard')

        if item:
            # Update existing item
            item.code = code
            item.name = name
            item.company = company
            item.category = category
            item.buying_price = buying_price
            item.selling_price = selling_price
            item.mrp = mrp
            item.stock_quantity = stock_quantity
            item.pcs_count = pcs_count
            if image:
                item.image = image
            item.save()
            messages.success(request, f'Item {item.name} updated successfully!')
        else:
            # Create new item
            item = Item.objects.create(
                code=code,
                name=name,
                company=company,
                category=category,
                buying_price=buying_price,
                selling_price=selling_price,
                mrp=mrp,
                stock_quantity=stock_quantity,
                pcs_count=pcs_count,
                image=image
            )
            messages.success(request, f'Item {item.name} added successfully!')

        return redirect('milk_agency:items_dashboard')

    context = {
        'item': item,
        'is_edit': item is not None
    }
    return render(request, 'milk_agency/items/add_item.html', context)

@login_required
def edit_item(request, item_id):
    return add_item(request, item_id)

@login_required
def delete_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)

    if request.method == 'POST':
        item_name = item.name
        item.delete()
        messages.success(request, f'Item {item_name} deleted successfully!')

    return redirect('milk_agency:items_dashboard')
