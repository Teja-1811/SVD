from django.urls import path
from . import views
from . import views_customer
from . import views_items
from . import views_bills
from . import views_bill_operations
from . import views_reports
from . import views_cashbook
from . import views_stock_dashboard
from . import views_companies
from . import views_sales_analytics
from . import views_payments
from . import views_category_sales
from . import views_customer_monthly_purchases
from . import views_orders_dashboard

from .monthly_sales_view import monthly_sales_summary, update_remaining_due

app_name = 'milk_agency'

urlpatterns = [
    # Home/Dashboard URLs
    path('', views.home, name='home'),

    # Sales Analytics URLs
    path('sales-dashboard/', views_sales_analytics.sales_dashboard, name='sales_dashboard'),
    path('api/sales/weekly/', views_sales_analytics.get_weekly_sales, name='weekly_sales_api'),
    path('api/sales/monthly/', views_sales_analytics.get_monthly_sales, name='monthly_sales_api'),
    path('api/sales/yearly/', views_sales_analytics.get_yearly_sales, name='yearly_sales_api'),
    path('api/sales/overall/', views_sales_analytics.get_overall_sales, name='overall_sales_api'),
    

    # Category Sales Statistics URLs
    path('category-sales-dashboard/', views_category_sales.category_sales_dashboard, name='category_sales_dashboard'),
    path('api/category-sales/today/', views_category_sales.get_today_category_sales, name='today_category_sales_api'),
    path('api/category-sales/week/', views_category_sales.get_week_category_sales, name='week_category_sales_api'),
    path('api/category-sales/month/', views_category_sales.get_month_category_sales, name='month_category_sales_api'),
    path('api/category-sales/year/', views_category_sales.get_year_category_sales, name='yearly_category_sales_api'),
    path('api/category-sales/monthly-history/', views_category_sales.get_monthly_category_history, name='monthly_category_history_api'),
    path('api/category-sales/yearly-history/', views_category_sales.get_yearly_category_history, name='yearly_category_history_api'),
    path('api/category-sales/summary/', views_category_sales.get_category_sales_summary, name='category_sales_summary_api'),

    # Customer Monthly Purchases URLs
    path('customer-monthly-purchases/', views_customer_monthly_purchases.customer_monthly_purchases_dashboard, name='customer_monthly_purchases_dashboard'),

    # Customer URLs
    path('add-customer/', views_customer.add_customer, name='add_customer'),
    path('edit-customer/<int:customer_id>/', views_customer.add_customer, name='edit_customer'),
    path('customer-data/', views_customer.customer_data, name='customer_data'),
    path('customer-data/update-balance/<int:customer_id>/', views_customer.update_customer_balance, name='update_customer_balance'),
    path('customer/freeze/<int:customer_id>/', views_customer.freeze_customer, name='freeze_customer'),

    # Items URLs
    path('items/', views_items.items_dashboard, name='items_dashboard'),
    path('add-item/', views_items.add_item, name='add_item'),
    path('edit-item/<int:item_id>/', views_items.edit_item, name='edit_item'),
    path('delete-item/<int:item_id>/', views_items.delete_item, name='delete_item'),

    # Bills URLs
    path('bills/', views_bills.bills_dashboard, name='bills_dashboard'),
    path('generate-bill/', views_bills.generate_bill, name='generate_bill'),
    path('generate-invoice-pdf/<int:bill_id>/', views_bills.generate_invoice_pdf, name='generate_invoice_pdf'),

    # Bills Modification URLs
    path('view-bill/<int:bill_id>/', views_bill_operations.view_bill, name='view_bill'),
    path('edit-bill/<int:bill_id>/', views_bill_operations.edit_bill, name='edit_bill'),
    path('get-bill-details/<int:bill_id>/', views_bill_operations.get_bill_details_ajax, name='get_bill_details_ajax'),

    # Reports URLs
    path('reports/', views_reports.reports_dashboard, name='reports_dashboard'),
    path('invoice-pdf-viewer/<int:invoice_id>/', views_reports.invoice_pdf_viewer, name='invoice_pdf_viewer'),
    path('monthly-sales-summary/', monthly_sales_summary, name='monthly_sales_summary'),
    path('update-remaining-due/', update_remaining_due, name='update_remaining_due'),

    # Cashbook URLs
    path('cashbook/', views_cashbook.cashbook, name='cashbook'),
    path('save_cash_in/', views_cashbook.save_cash_in, name='save_cash_in'),
    path('save_expense/', views_cashbook.save_expense, name='save_expense'),
    path('expenses-list/', views_cashbook.expenses_list, name='expenses_list'),
    path('save_bank_balance/', views_cashbook.save_bank_balance, name='save_bank_balance'),

    # Stock Dashboard URLs
    path('stock-dashboard/', views_stock_dashboard.stock_dashboard, name='stock_dashboard'),
    path('update-stock/', views_stock_dashboard.update_stock, name='update_stock'),
    path('api/stock-data/', views_stock_dashboard.stock_data_api, name='stock_data_api'),

    # Legacy invoice URL (keeping for backward compatibility)
    path('invoice/', views_bills.generate_bill, name='invoice'),

    # Payments Dashboard URL
    path('payments/', views_payments.payments_dashboard, name='payments_dashboard'),

    # Companies Dashboard URL
    path('companies/', views_companies.companies_dashboard, name='companies_dashboard'),

    # Product Pages
    path('products/dodla/', views.dodla_products, name='dodla_products'),
    path('products/jersey/', views.jersey_products, name='jersey_products'),

    # Admin Orders Dashboard URLs
    path('admin-orders-dashboard/', views_orders_dashboard.admin_orders_dashboard, name='admin_orders_dashboard'),
    path('confirm-order/<int:order_id>/', views_orders_dashboard.confirm_order, name='confirm_order'),
    path('reject-order/<int:order_id>/', views_orders_dashboard.reject_order, name='reject_order'),

]
