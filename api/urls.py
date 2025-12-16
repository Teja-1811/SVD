from django.urls import path
from .views import login_api
from .products import *
from .customer_place_order import *
from .admin_dashboard import *
from .customer_dashboard import *
from .customer_invoice_data import *
from .customer_payment import record_customer_payment

urlpatterns = [
    # Auth / Login
    path('auth/login/', login_api, name='login_api'),

    # Admin Dashboard Counts
    path('dashboard-counts/', dashboard_api, name='dashboard_counts_api'),

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
