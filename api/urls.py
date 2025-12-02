
from django.urls import path
from .views import login_api
from .admin_dashboard import dashboard_api as dashboard_counts_api

urlpatterns = [
    path('auth/login/', login_api, name='login_api'),

    # Items list API (Android needs this)
    #path('items/', items_api, name='items_api'),

    # Dashboard counts API (Android needs this)
    path('dashboard-counts/', dashboard_counts_api, name='dashboard_counts_api'),
]
