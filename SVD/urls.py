from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.shortcuts import render
from django.http import FileResponse, Http404
from milk_agency.models import Item, Company
from pathlib import Path
from .firebase_views import firebase_messaging_sw
from milk_agency import paytm as paytm_views


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


def media_file_view(request, path):
    media_root = Path(settings.MEDIA_ROOT).resolve()
    requested_path = (media_root / path).resolve()

    if media_root not in requested_path.parents and requested_path != media_root:
        raise Http404("Invalid media path")

    if not requested_path.is_file():
        raise Http404("Media file not found")

    return FileResponse(open(requested_path, "rb"))


# IMPORTANT: Use correct project path
handler404 = "SVD.urls.custom_404_view"


# ======================================================
# MAIN URL ROUTES
# ======================================================
urlpatterns = [
    path('admin/', admin.site.urls),
    path('firebase-messaging-sw.js', firebase_messaging_sw, name='firebase_messaging_sw'),
    path('users/orders/paytm/callback/', paytm_views.user_orders_paytm_callback, name='users_paytm_callback'),
    path('customer/paytm/callback/', paytm_views.customer_portal_paytm_callback, name='customer_portal_paytm_callback'),
    path('users/subscriptions/paytm/callback/', paytm_views.subscription_paytm_callback, name='subscription_paytm_callback'),

    # favicon
    path(
        'favicon.ico',
        RedirectView.as_view(url='/static/favicon.ico', permanent=True)
    ),
    path(
        'android-chrome-192x192.png',
        RedirectView.as_view(url='/static/android-chrome-192x192.png', permanent=True)
    ),
    path(
        'android-chrome-512x512.png',
        RedirectView.as_view(url='/static/android-chrome-512x512.png', permanent=True)
    ),
    path(
        'apple-touch-icon.png',
        RedirectView.as_view(url='/static/apple-touch-icon.png', permanent=True)
    ),

    # Public website
    path('', index_view, name='index'),
    path('images/<path:path>', media_file_view, name='media_file'),

    # Apps
    path('customer/', include('customer_portal.urls', namespace='customer_portal')),
    path('users/', include('users.urls', namespace='users')),
    path('general_store/', include('general_store.urls')),
    path('milk_agency/', include('milk_agency.urls', namespace='milk_agency')),
    path('api/', include('api.urls')),
]


# ======================================================
# STATIC & MEDIA
# Keep local static/media asset routes available even when DEBUG is False,
# because this project is commonly run via Django's built-in server.
# ======================================================
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += staticfiles_urlpatterns()
