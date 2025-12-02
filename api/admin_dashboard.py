from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum
from django.utils.timezone import now
from milk_agency.models import Customer, Item, Bill

@api_view(["GET"])
def dashboard_counts_api(request):

    # Total customers
    total_customers = Customer.objects.count()

    # Total items
    total_items = Item.objects.count()

    # Today's date
    today = now().date()

    # Today Sales
    sales_today = Bill.objects.filter(invoice_date=today).aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    # Total due amount
    total_dues = Bill.objects.aggregate(
        total=Sum("op_due_amount")
    )["total"] or 0

    # Stock summary
    stock_value = Item.objects.aggregate(
        total=Sum("stock_quantity") * Sum("buying_price")
    )["total"] or 0

    # Low stock count
    low_stock = Item.objects.filter(stock_quantity__lt=10).count()

    # Out of stock count
    out_of_stock = Item.objects.filter(stock_quantity=0).count()

    return Response({
        "customers": total_customers,
        "items": total_items,
        "sales_today": sales_today,
        "dues": total_dues,
        "total_stock_items": stock_value,
        "low_stock_items": low_stock,
        "out_of_stock_items": out_of_stock,
    })
