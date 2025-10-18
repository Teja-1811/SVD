from django.urls import path
from . import views

app_name = 'general_store'

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/<int:pk>/edit/', views.edit_product, name='edit_product'),
    path('sales/', views.sales_list, name='sales_list'),
    path('sales/add/', views.add_sale, name='add_sale'),
]
