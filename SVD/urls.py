from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView, RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib import messages
from django.shortcuts import render

def index_view(request):
    from milk_agency.models import Item, Company

    # Only show products that are not frozen
    products = Item.objects.all().order_by('id')

    # Check if at least ONE item is unfrozen
    has_active_items = Item.objects.filter(frozen=False).exists()

    # Show company list only if active items exist
    companies = Company.objects.all() if has_active_items else []

    return render(request, 'index.html', {
        'products': products,
        'companies': companies,
        'show_company_logos': has_active_items
    })


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
