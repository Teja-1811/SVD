from django.contrib import admin
from .models import Company, StockInEntry

# Register your models here.
admin.site.register(Company)
admin.site.register(StockInEntry)
