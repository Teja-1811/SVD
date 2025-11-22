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

# Import for serving the main index page
from django.shortcuts import render

def index_view(request):
    """Serve the main index/landing page"""
    from milk_agency.models import Item
    # Get only items that are in stock (stock_quantity > 0)
    products = Item.objects.filter(stock_quantity__gt=0).order_by('name')
    context = {
        'products': products,
    }
    return render(request, 'index.html', context)

# Product pages removed - functionality no longer available

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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Serve static files from STATICFILES_DIRS during development
    import os
    from django.conf import settings
    for static_dir in settings.STATICFILES_DIRS:
        if os.path.exists(static_dir):
            urlpatterns += static(settings.STATIC_URL, document_root=static_dir)
