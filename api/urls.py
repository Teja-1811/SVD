from django.urls import path
from .views import login_api
from .admin_dashboard import *
from .customer import *

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

    # -------------------------
    # CUSTOMER INVOICE APIS
    # -------------------------

    # Invoice Summary API
    path('customer/invoices/summary/', customer_invoice_summary_api, name='customer_invoice_summary_api'),

    # Invoice List API
    path('customer/invoices/', customer_invoice_list_api, name='customer_invoice_list_api'),

    # Invoice PDF Download API
    path('customer/invoice/download/', customer_invoice_download_api, name='customer_invoice_download_api'),
]
