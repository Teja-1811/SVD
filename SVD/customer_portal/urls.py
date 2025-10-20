from django.urls import path
from django.views.generic.base import RedirectView
from . import views

app_name = 'customer_portal'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('orders/', views.customer_orders_dashboard, name='customer_orders_dashboard'),
    path('reports/', views.reports_dashboard, name='reports_dashboard'),
    path('bill-details/<int:bill_id>/', views.bill_details, name='bill_details'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('logout/', views.logout_view, name='logout'),
]
