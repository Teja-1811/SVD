from django.urls import path
from django.views.generic.base import RedirectView
from . import views
from milk_agency import paytm as paytm_views
from .push_views import register_push_device, unregister_push_device

app_name = 'customer_portal'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('orders/', views.customer_orders_dashboard, name='customer_orders_dashboard'),
    path('orders/place/', views.place_order, name='place_order'),
    path("orders/history/", views.order_history, name="order_history"),
    path("orders/last/", views.last_order_details, name="last_order_details"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/<int:order_id>/delete/", views.delete_order, name="delete_order"),
    path('reports/', views.reports_dashboard, name='reports_dashboard'),
    path('bill-details/<int:bill_id>/', views.bill_details, name='bill_details'),
    path("collect-payment/", views.collect_payment, name="collect_payment"),
    path("collect-payment/start/", views.start_collect_payment, name="start_collect_payment"),
    path("paytm/callback/", paytm_views.customer_portal_paytm_callback, name="paytm_callback"),
    path('update-profile/', views.update_profile, name='update_profile'),

    path("notifications/push/register/", register_push_device, name="push_device_register"),
    path("notifications/push/unregister/", unregister_push_device, name="push_device_unregister"),
    path('logout/', views.logout_user, name='logout'),
]
