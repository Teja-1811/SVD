from django.contrib import admin
from .models import CustomerOrder, CustomerOrderItem

@admin.register(CustomerOrder)
class CustomerOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'status', 'order_date', 'total_amount')
    list_filter = ('status', 'order_date')
    search_fields = ('order_number', 'customer__name')

@admin.register(CustomerOrderItem)
class CustomerOrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'item', 'requested_quantity', 'requested_price')
    list_filter = ('order__status',)
    search_fields = ('item__name', 'order__order_number')
