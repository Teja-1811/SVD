from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView, RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib import messages
from django.shortcuts import render

def index_view(request):
    from milk_agency.models import Item
    products = Item.objects.filter(stock_quantity__gt=0).order_by('name')
    show_company_logos = Item.objects.filter(frozen=False).exists()
    return render(request, 'index.html', {'products': products, 'show_company_logos': show_company_logos})

def handler404(request, exception):
    messages.error(request, "Please Login")
    return redirect('index')

urlpatterns = [
    path('admin/', admin.site.urls),

    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),

    path('', index_view, name='index'),
    path('customer/', include('customer_portal.urls', namespace='customer_portal')),
    path('general_store/', include('general_store.urls')),
    path('milk_agency/', include('milk_agency.urls', namespace='milk_agency')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    import os
    for static_dir in settings.STATICFILES_DIRS:
        if os.path.exists(static_dir):
            urlpatterns += static(settings.STATIC_URL, document_root=static_dir)
