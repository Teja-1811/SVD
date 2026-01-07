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
