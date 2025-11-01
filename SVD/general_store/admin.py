from django.contrib import admin
from .models import Category, Product, Customer, Sale, SaleItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'buying_price', 'mrp', 'stock_quantity')
    list_filter = ('category',)
    search_fields = ('name', 'category__name')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'address', 'balance')
    search_fields = ('name', 'phone')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer', 'invoice_date', 'total_amount', 'due_amount', 'profit')
    list_filter = ('invoice_date', 'customer')
    search_fields = ('invoice_number', 'customer__name')

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ('sale', 'product', 'quantity', 'price_per_unit', 'discount', 'total_amount')
    list_filter = ('sale__invoice_date', 'product')
    search_fields = ('product__name', 'sale__invoice_number')
