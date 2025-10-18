"""
URL configuration for SVD project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib import messages

# Import the category sales views for root-level API endpoints
from milk_agency import views_category_sales
from milk_agency import views_sales_analytics

# Import for serving the main index page
from django.shortcuts import render

def index_view(request):
    """Serve the main index/landing page"""
    return render(request, 'index.html')

# Import views for product pages
from milk_agency.views import dodla_products, jersey_products

def handler404(request, exception):
    """Custom 404 handler that redirects to index with login message"""
    messages.error(request, "Please Login")
    return redirect('index')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index_view, name='index'),
    path('customer/', include('customer_portal.urls', namespace='customer_portal')),
    path('general_store/', include('general_store.urls')),
    path('milk_agency/', include('milk_agency.urls', namespace='milk_agency')),
    # Removed duplicate customer_portal include to fix namespace conflict and 404 at root
    # path('customer/', include('customer_portal.urls', namespace='customer_portal')),

    # Root-level API endpoints for category sales (to match frontend expectations)
    path('api/category-sales/today/', views_category_sales.get_today_category_sales, name='api_today_category_sales'),
    path('api/category-sales/summary/', views_category_sales.get_category_sales_summary, name='api_category_sales_summary'),
    path('api/category-sales/week/', views_category_sales.get_week_category_sales, name='api_week_category_sales'),
    path('api/category-sales/month/', views_category_sales.get_month_category_sales, name='api_month_category_sales'),
    path('api/category-sales/year/', views_category_sales.get_year_category_sales, name='api_yearly_category_sales'),
    path('api/category-sales/monthly-history/', views_category_sales.get_monthly_category_history, name='api_monthly_category_history'),
    path('api/category-sales/yearly-history/', views_category_sales.get_yearly_category_history, name='api_yearly_category_history'),

    # Root-level API endpoints for sales analytics (to match frontend expectations)
    path('api/sales/summary/', views_sales_analytics.get_sales_summary, name='api_sales_summary'),
    path('api/sales/weekly/', views_sales_analytics.get_weekly_sales, name='api_weekly_sales'),
    path('api/sales/monthly/', views_sales_analytics.get_monthly_sales, name='api_monthly_sales'),
    path('api/sales/yearly/', views_sales_analytics.get_yearly_sales, name='api_yearly_sales'),
    path('api/sales/overall/', views_sales_analytics.get_overall_sales, name='api_overall_sales'),
    path('api/sales/filter/', views_sales_analytics.get_filtered_sales, name='api_filtered_sales'),

    # Product Pages
    path('products/dodla/', dodla_products, name='dodla_products'),
    path('products/jersey/', jersey_products, name='jersey_products'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Serve static files from STATICFILES_DIRS during development
    import os
    from django.conf import settings
    for static_dir in settings.STATICFILES_DIRS:
        if os.path.exists(static_dir):
            urlpatterns += static(settings.STATIC_URL, document_root=static_dir)
