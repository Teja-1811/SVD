from django.urls import path
from .views import login_api
from .products import *
from .customer_place_order import *
from .admin_dashboard import *
from .customer_dashboard import *
from .customer_invoice_data import *
from .customer_payment import record_customer_payment
from .admin_customer import *
from .admin_items import *
from .admin_bills import *
from .admin_cashbook import *
from .admin_payments import *
from .admin_orders_dashboard import *
from .admin_stock_dashboard import *
from .admin_customer_payments import *
from .admin_companies import *
from .admin_monthly_sales_summary import api_monthly_sales_summary

urlpatterns = [
    # Auth / Login
    path('auth/login/', login_api, name='login_api'),

    # Admin Dashboard Counts
    path('dashboard-counts/', dashboard_api, name='dashboard_counts_api'),
    
    #Customer Dashboard APIs
    path('customer-list/', api_customer_list, name='api_customer_list'),
    path('customer-detail/<int:pk>/', api_customer_detail, name='api_customer_detail'),
    path('customer-freeze/<int:pk>/', api_toggle_freeze, name='api_toggle_freeze'),
    path('customer-balance/<int:pk>/', api_update_balance, name='api_update_balance'),
    path('customer-add/', api_add_edit_customer, name='api_add_customer'),
    
    # Companies APIs
    path('companies/', companies_list_api, name='companies_list_api'),
    path('companies/add/', add_company_api, name='add_company_api'),
    path('companies/edit/<int:company_id>/', edit_company_api, name='edit_company_api'),
    path('companies/items/<int:company_id>/', company_items_api, name='company_items_api'),
    
    
    # Items Management APIs
    path('items/categories/', get_categories, name='get_categories'),
    path('items/by-category/', get_items_by_category, name='get_items_by_category'),
    path('items/add/', add_item, name='add_item'),
    path('items/edit/<int:pk>/', edit_item, name='edit_item'),
    
    # Bills Management APIs
    path('bills/list/', api_list_bills, name='api_list_bills'),
    path('bills/create/', api_create_bill, name='api_create_bill'),
    path('bills/<int:bill_id>/', api_bill_detail, name='api_bill_detail'),
    path('bills/<int:bill_id>/items/', api_bill_items, name='api_bill_items'),
    path('bills/<int:bill_id>/download/', api_download_bill, name='api_download_bill'),
    path('bills/<int:bill_id>/delete/', api_delete_bill, name='api_delete_bill'),
    path('bills/<int:bill_id>/edit/', api_edit_bill, name='api_edit_bill'),
    
    #Cashbook Management APIs
    path('cashbook/entries/', api_cashbook_dashboard, name='api_cashbook_entries'),
    path('cashbook/save-cash/', api_save_cash_in, name='api_add_cash_in'),
    path('cashbook/save-bank/', api_save_bank_balance, name='api_add_cash_out'),
    path('cashbook/add-expense/', api_add_expense, name='api_add_expense'),
    path('cashbook/edit-expense/<int:expense_id>/', api_edit_expense, name='api_edit_expense'),
    path('cashbook/expenses/', api_list_expenses, name='api_list_expenses'),
    path('cashbook/delete-expense/<int:expense_id>/', api_delete_expense, name='api_delete_expense'),
    
    #Company Payments APIs
    path('payments/dashboard/', api_payments_dashboard, name='api_payments_dashboard'),
    path('payments/save-daily/', api_save_daily_payments, name='api_save_daily_payment'),
    path('payments/monthly-summary/', api_monthly_payment_summary, name='api_monthly_payment_summary'),
    
    #Admin Orders Dashboard APIs
    path('orders/dashboard/', api_admin_orders_dashboard, name='api_admin_orders_dashboard'),
    path('orders/<int:order_id>/detail/', api_order_detail, name='api_order_detail'),
    path('orders/<int:order_id>/confirm/', api_confirm_order, name='api_confirm_order'),
    path('orders/<int:order_id>/cancel/', api_reject_order, name='api_cancel_order'),
    
    #Admin Stock Dashboard API
    path('stock/dashboard/', stock_dashboard_api, name='stock_dashboard_api'),
    path('stock/update/', update_stock_api, name='update_stock_api'),
    
    # Monthly Sales Summary API
    path('sales/monthly-summary/', api_monthly_sales_summary, name='api_monthly_sales_summary'),
    
    # Customer Payments API
    path('customer-payments/', customer_payments_api, name='customer_payments_api'),
    path('customer-payments/update-status/<int:payment_id>/', update_payment_status_api, name='update_payment_status_api'),
    path('customer-payments/delete/<int:payment_id>/', delete_payment_api, name='delete_payment_api'),
    
    

    # Customer Dashboard
    path('customer-dashboard/', customer_dashboard_api, name='customer_dashboard_api'),
    
    # Items APIs
    path('categories/', categories_api, name='categories_api'),
    path('products/', products_api, name='products_api'),
    
    # Place Order API
    path('place-order/', place_order_api, name='place_order_api'),

    # -------------------------
    # CUSTOMER INVOICE APIS
    # -------------------------

    # Invoice Summary API
    path('customer/invoices/summary/', customer_invoice_summary_api, name='customer_invoice_summary_api'),

    # Invoice List API
    path('customer/invoices/', customer_invoice_list_api, name='customer_invoice_list_api'),

    # Invoice PDF Download API
    path('customer/invoice/download/', customer_invoice_download_api, name='customer_invoice_download_api'),
    
    # Invoice Details API
    path('customer/invoice/details/', customer_invoice_details_api, name='customer_invoice_details_api'),
    
    # Customer Payment API
    path('customer/payment/record/', record_customer_payment, name='record_customer_payment'),
]
