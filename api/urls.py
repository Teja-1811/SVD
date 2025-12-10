
from django.urls import path
from .views import login_api
from .admin_dashboard import *
from .customer import *

urlpatterns = [
    path('auth/login/', login_api, name='login_api'),

    # Admin Dashboard counts API (Android needs this)
    path('dashboard-counts/', dashboard_api, name='dashboard_counts_api'),
    
    # Customer Dashboard API
    path('customer-dashboard/', customer_dashboard_api, name='customer_dashboard_api'),
    path('categories/', categories_api, name='categories_api'),
    path('customer-items/', customer_items_api, name='customer_items_api'),
]
