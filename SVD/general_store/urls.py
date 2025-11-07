from django.urls import path
from . import views_dashboard, views_products, views_customers, views_sales, views_cashbook

app_name = 'general_store'

urlpatterns = [
    # Dashboard URLs
    path('', views_dashboard.home, name='home'),
    path('sales-trends/', views_dashboard.sales_trends, name='sales_trends'),

    # Product URLs
    path('products/', views_products.product_list, name='product_list'),
    path('products/add/', views_products.add_product, name='add_product'),
    path('products/<int:pk>/edit/', views_products.edit_product, name='edit_product'),

    # Customer URLs
    path('customers/', views_customers.customer_list, name='customer_list'),
    path('customers/add/', views_customers.add_customer, name='add_customer'),
    path('customers/<int:pk>/edit/', views_customers.edit_customer, name='edit_customer'),

    # Sales URLs
    path('sales/', views_sales.sales_list, name='sales_list'),
    path('sales/add/', views_sales.add_sale, name='add_sale'),
    path('sales/<int:pk>/view/', views_sales.view_sale, name='view_sale'),
    path('sales/<int:pk>/edit/', views_sales.edit_sale, name='edit_sale'),
    path('sales/<int:pk>/delete/', views_sales.delete_sale, name='delete_sale'),
    path('sales/<int:pk>/pdf/', views_sales.generate_sale_pdf, name='generate_sale_pdf'),
    path('anonymous-bills/', views_sales.anonymous_bills_list, name='anonymous_bills_list'),

    # Cashbook URLs
    path('cashbook/', views_cashbook.cashbook, name='cashbook'),
    path('save_cash_in/', views_cashbook.save_cash_in, name='save_cash_in'),
    path('save_expense/', views_cashbook.save_expense, name='save_expense'),
    path('save_investment/', views_cashbook.save_investment, name='save_investment'),
    path('investments-list/', views_cashbook.investments_list, name='investments_list'),
    path('expenses-list/', views_cashbook.expenses_list, name='expenses_list'),
    path('edit-expense/<int:pk>/', views_cashbook.edit_expense, name='edit_expense'),
    path('delete-expense/<int:pk>/', views_cashbook.delete_expense, name='delete_expense'),
    path('save_bank_balance/', views_cashbook.save_bank_balance, name='save_bank_balance'),
]
