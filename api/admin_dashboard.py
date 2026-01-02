from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Sum, F
from django.utils.timezone import now
from milk_agency.models import Customer, Item, Bill
from customer_portal.models import CustomerOrder


@api_view(["GET"])
def dashboard_api(request):

    # Total customers
    total_customers = Customer.objects.count()

    # Total items
    total_items = Item.objects.count()

    today = now().date()

    # Today Sales
    sales_today = Bill.objects.filter(invoice_date=today).aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    # Total dues
    total_dues = Customer.objects.aggregate(total=Sum("due"))["total"] or 0

    # Stock Value
    stock_value = (
        Item.objects.aggregate(total=Sum(F("stock_quantity") * F("buying_price")))["total"]
        or 0
    )

    # Low stock
    low_stock = Item.objects.filter(stock_quantity__lt=10).count()

    # Out of stock
    out_of_stock = Item.objects.filter(stock_quantity=0).count()

    # Pending orders
    pending_orders = CustomerOrder.objects.filter(status='pending').count()

    # ============ CUSTOMERS NOT ORDERED TODAY ============
    customers_no_orders_today_qs = Customer.objects.exclude(
        id__in=CustomerOrder.objects.filter(order_date__date=today)
        .values_list('customer_id', flat=True)
    )

    customers_no_orders_today = customers_no_orders_today_qs.count()

    # Return list of customers (name + phone)
    customers_no_orders_list = [
        {
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
        }
        for c in customers_no_orders_today_qs
    ]

    return Response({
        "customers": total_customers,
        "items": total_items,
        "sales_today": sales_today,
        "dues": total_dues,
        "total_stock_items": stock_value,
        "low_stock_items": low_stock,
        "out_of_stock_items": out_of_stock,
        "pending_orders": pending_orders,

        # NEW FIELDS
        "customers_no_orders_today_count": customers_no_orders_today,
        "customers_no_orders_today_list": customers_no_orders_list,
    })
