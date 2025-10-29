from django.urls import path
from . import views

app_name = 'general_store'

urlpatterns = [
    path('', views.home, name='home'),
    path('sales-trends/', views.sales_trends, name='sales_trends'),
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/<int:pk>/edit/', views.edit_product, name='edit_product'),
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/<int:pk>/edit/', views.edit_customer, name='edit_customer'),
    path('sales/', views.sales_list, name='sales_list'),
    path('sales/add/', views.add_sale, name='add_sale'),
    path('sales/<int:pk>/view/', views.view_sale, name='view_sale'),
    path('sales/<int:pk>/edit/', views.edit_sale, name='edit_sale'),
    path('sales/<int:pk>/delete/', views.delete_sale, name='delete_sale'),
    path('sales/<int:pk>/pdf/', views.generate_sale_pdf, name='generate_sale_pdf'),
    path('anonymous-bills/', views.anonymous_bills_list, name='anonymous_bills_list'),
]
