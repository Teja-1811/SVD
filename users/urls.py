from django.urls import path

from .dashboard import dashboard
from .invoices import invoice_detail, invoices_page
from .offers import offers_page
from .orders import (
    cancel_order,
    delete_order_page,
    order_detail_page,
    order_history_page,
    orders_page,
    paytm_callback,
    paytm_checkout,
    place_order,
    prepare_payment_order,
)
from .subscriptions import subscriptions_page


app_name = "users"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("orders/", orders_page, name="orders"),
    path("orders/history/", order_history_page, name="order_history"),
    path("orders/<int:order_id>/", order_detail_page, name="order_detail"),
    path("orders/place/", place_order, name="place_order"),
    path("orders/payment/prepare/", prepare_payment_order, name="prepare_payment_order"),
    path("orders/<int:order_id>/paytm/checkout/", paytm_checkout, name="paytm_checkout"),
    path("orders/paytm/callback/", paytm_callback, name="paytm_callback"),
    path("orders/<int:order_id>/cancel/", cancel_order, name="cancel_order"),
    path("orders/<int:order_id>/delete/", delete_order_page, name="delete_order"),
    path("offers/", offers_page, name="offers"),
    path("subscriptions/", subscriptions_page, name="subscriptions"),
    path("invoices/", invoices_page, name="invoices"),
    path("invoices/<int:bill_id>/", invoice_detail, name="invoice_detail"),
]
