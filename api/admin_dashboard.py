from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, F
from django.utils.timezone import now

from milk_agency.models import Customer, Item, Bill


@api_view(['GET'])
def dashboard_api(request):

    # Total customers
    total_customers = Customer.objects.count()

    # Total items
    total_items = Item.objects.count()

    # Today Sales
    today = now().date()
    sales_today = Bill.objects.filter(date=today).aggregate(
        total=Sum("amount")
    )["total"] or 0

    # Total due from customers
    total_dues = Customer.objects.aggregate(total=Sum("due"))["total"] or 0

    # Stock summary
    stock_value = (
        Item.objects.aggregate(total=Sum(F("stock_quantity") * F("buying_price")))["total"]
        or 0
    )
    
    total_stock_items = Item.objects.filter(frozen=False).count()
    low_stock_items = Item.objects.filter(stock_quantity__lt=F("pcs_count")).count()
    out_of_stock_items = Item.objects.filter(stock_quantity=0).count()

    return Response({
        "customers": total_customers,
        "items": total_items,
        "sales_today": sales_today,
        "dues": total_dues,
        "stock_value": stock_value,
        "total_stock_items": total_stock_items,
        "low_stock_items": low_stock_items,
        "out_of_stock_items": out_of_stock_items,
    })
