from django.urls import path
from . import views
from . import views_customer
from . import views_items
from . import views_bills
from . import views_bill_operations

from . import views_cashbook
from . import views_stock_dashboard
from . import views_companies
from . import views_payments
from . import views_customer_monthly_purchases
from . import views_orders_dashboard
from . import views_sales_summary
from . import views_dodla

from .monthly_sales_summary import monthly_sales_summary, update_remaining_due, generate_monthly_sales_pdf



app_name = 'milk_agency'

urlpatterns = [
    # Home/Dashboard URLs
    path('', views.home, name='home'),

    # Customer Monthly Purchases URLs
    path('customer-monthly-purchases/', views_customer_monthly_purchases.customer_monthly_purchases_dashboard, name='customer_monthly_purchases_dashboard'),

    # Customer URLs
    path('add-customer/', views_customer.add_customer, name='add_customer'),
    path('edit-customer/<int:customer_id>/', views_customer.add_customer, name='edit_customer'),
    path('customer-data/', views_customer.customer_data, name='customer_data'),
    path('customer-data/update-balance/<int:customer_id>/', views_customer.update_customer_balance, name='update_customer_balance'),
    path('customer/freeze/<int:customer_id>/', views_customer.freeze_customer, name='freeze_customer'),

    # Items URLs
    path('items/', views_items.items_dashboard, name='items_dashboard'),
    path('add-item/', views_items.add_item, name='add_item'),
    path('edit-item/<int:item_id>/', views_items.edit_item, name='edit_item'),
    path('freeze-item/<int:item_id>/', views_items.freeze_item, name='freeze_item'),

    # Bills URLs
    path('bills/', views_bills.bills_dashboard, name='bills_dashboard'),
    path('anonymous-bills/', views_bills.anonymous_bills_list, name='anonymous_bills_list'),
    path('generate-bill/', views_bills.generate_bill, name='generate_bill'),
    path('generate-invoice-pdf/<int:bill_id>/', views_bills.generate_invoice_pdf, name='generate_invoice_pdf'),

    # Bills Modification URLs
    path('view-bill/<int:bill_id>/', views_bill_operations.view_bill, name='view_bill'),
    path('edit-bill/<int:bill_id>/', views_bill_operations.edit_bill, name='edit_bill'),
    path('delete-bill/<int:bill_id>/', views_bill_operations.delete_bill, name='delete_bill'),
    path('get-bill-details/<int:bill_id>/', views_bill_operations.get_bill_details_ajax, name='get_bill_details_ajax'),

    # Reports URLs
    path('monthly-sales-summary/', monthly_sales_summary, name='monthly_sales_summary'),
    path('generate-monthly-sales-pdf/', generate_monthly_sales_pdf, name='generate_monthly_sales_pdf'),
    path('update-remaining-due/', update_remaining_due, name='update_remaining_due'),
    path('sales-summary-by-category/', views_sales_summary.sales_summary_by_category, name='sales_summary_by_category'),

    # Cashbook URLs
    path('cashbook/', views_cashbook.cashbook, name='cashbook'),
    path('save_cash_in/', views_cashbook.save_cash_in, name='save_cash_in'),
    path('save_expense/', views_cashbook.save_expense, name='save_expense'),
    path('expenses-list/', views_cashbook.expenses_list, name='expenses_list'),
    path('save_bank_balance/', views_cashbook.save_bank_balance, name='save_bank_balance'),

    # Stock Dashboard URLs
    path('stock-dashboard/', views_stock_dashboard.stock_dashboard, name='stock_dashboard'),
    path('update-stock/', views_stock_dashboard.update_stock, name='update_stock'),
    path('api/stock-data/', views_stock_dashboard.stock_data_api, name='stock_data_api'),

    # Legacy invoice URL (keeping for backward compatibility)
    path('invoice/', views_bills.generate_bill, name='invoice'),

    # Payments Dashboard URL
    path('payments/', views_payments.payments_dashboard, name='payments_dashboard'),

    # Companies Dashboard URL
    path('companies/', views_companies.companies_dashboard, name='companies_dashboard'),

    # Product Pages - removed unused product pages

    # Admin Orders Dashboard URLs
    path('admin-orders-dashboard/', views_orders_dashboard.admin_orders_dashboard, name='admin_orders_dashboard'),
    path('confirm-order/<int:order_id>/', views_orders_dashboard.confirm_order, name='confirm_order'),
    path('reject-order/<int:order_id>/', views_orders_dashboard.reject_order, name='reject_order'),

    # Dodla Products URL
    path('dodla-products/', views_dodla.dodla_products, name='dodla_products'),



]
