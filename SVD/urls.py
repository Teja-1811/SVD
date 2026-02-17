from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from milk_agency.models import Item, Company


# ======================================================
# PUBLIC INDEX PAGE
# ======================================================
def index_view(request):
    from milk_agency.models import Item, Company

    # Active products only
    products = Item.objects.filter(frozen=False).select_related('company')

    # All companies
    companies = Company.objects.all()

    # Group products by company id
    products_by_company = {}
    for product in products:
        if product.company_id:
            products_by_company.setdefault(product.company_id, []).append(product)

    return render(request, 'index.html', {
        'products': products,  # optional
        'companies': companies,
        'products_by_company': products_by_company,  # 🔥 REQUIRED
    })



# ======================================================
# CUSTOM 404 PAGE (SAFE)
# ======================================================
def custom_404_view(request, exception):
    return render(request, "404.html", status=404)


# IMPORTANT: Use correct project path
handler404 = "SVD.urls.custom_404_view"


# ======================================================
# MAIN URL ROUTES
# ======================================================
urlpatterns = [
    path('admin/', admin.site.urls),

    # favicon
    path(
        'favicon.ico',
        RedirectView.as_view(url='/static/favicon.ico', permanent=True)
    ),

    # Public website
    path('', index_view, name='index'),

    # Apps
    path('customer/', include('customer_portal.urls', namespace='customer_portal')),
    path('general_store/', include('general_store.urls')),
    path('milk_agency/', include('milk_agency.urls', namespace='milk_agency')),
    path('api/', include('api.urls')),
]


# ======================================================
# STATIC & MEDIA (DEBUG ONLY)
# ======================================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
