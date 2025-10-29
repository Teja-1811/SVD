from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def dodla_products(request):
    """View to display all Dodla dairy products from database."""
    from milk_agency.models import Item

    # Get all items from database, ordered by category and name
    items = Item.objects.all().order_by('category', 'name')

    # Group products by category
    categorized_products = {}
    for item in items:
        category = item.category or 'Other'
        if category not in categorized_products:
            categorized_products[category] = []
        categorized_products[category].append(item)

    context = {
        'categorized_products': categorized_products,
    }

    return render(request, 'dodla_products.html', context)
