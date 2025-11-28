from django.urls import path
from .views import login_api

urlpatterns = [
    path('auth/login/', login_api, name='login_api'),
]
