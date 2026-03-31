from django.urls import path

from .dashboard import dashboard
from .offers import offers_page
from .orders import orders_page, place_order
from .subscriptions import subscriptions_page


app_name = "users"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("orders/", orders_page, name="orders"),
    path("orders/place/", place_order, name="place_order"),
    path("offers/", offers_page, name="offers"),
    path("subscriptions/", subscriptions_page, name="subscriptions"),
]
