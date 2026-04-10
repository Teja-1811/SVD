from django.urls import path
from . import views
from . import views_customer
from . import views_items
from . import views_bills
from . import views_bill_operations
from . import views_cashbook
from . import views_stock_dashboard
from . import views_companies
from . import views_payments
from . import customer_payments_views
from . import views_orders_dashboard
from . import views_sales_summary

from .monthly_sales_summary import monthly_sales_summary, update_remaining_due, generate_monthly_sales_pdf

from . import views_users
from . import subscriptions
from . import views_offers



app_name = 'milk_agency'

urlpatterns = [
    # Home/Dashboard URLs
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('privacy-policy/', views.privacy, name='privacy_policy'),
    path('terms-and-conditions/', views.terms, name='terms_and_conditions'),
    path('refund-policy/', views.refund, name='refund_policy'),
    path('checkout/', views.checkout, name='checkout'),
    path('admin-enquiries/', views.admin_enquiries, name='admin_enquiries'),

    # Customer Monthly Purchases URLs - removed, functionality no longer available

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
    path('freeze-item/<int:item_id>/', views_items.freeze_item, name='freeze_item'),

    # Bills URLs
    path('bills/', views_bills.bills_dashboard, name='bills_dashboard'),
    path('generate-bill/', views_bills.generate_bill, name='generate_bill'),
    path('generate-invoice-pdf/<int:bill_id>/', views_bills.generate_invoice_pdf, name='generate_invoice_pdf'),

    # Bills Modification URLs
    path('view-bill/<int:bill_id>/', views_bill_operations.view_bill, name='view_bill'),
    path('public-invoice/<int:bill_id>/<str:token>/', views_bill_operations.public_invoice_detail, name='public_invoice_detail'),
    path('edit-bill/<int:bill_id>/', views_bill_operations.edit_bill, name='edit_bill'),
    path('delete-bill/<int:bill_id>/', views_bill_operations.delete_bill, name='delete_bill'),
    path('get-bill-details/<int:bill_id>/', views_bill_operations.get_bill_details_ajax, name='get_bill_details_ajax'),

    # Reports URLs
    path('monthly-sales-summary/', monthly_sales_summary, name='monthly_sales_summary'),
    path('generate-monthly-sales-pdf/', generate_monthly_sales_pdf, name='generate_monthly_sales_pdf'),
    path('update-remaining-due/', update_remaining_due, name='update_remaining_due'),
    path('sales-summary-by-category/', views_sales_summary.sales_summary_by_category, name='sales_summary_by_category'),

    # Cashbook URLs
    path('cashbook/', views_cashbook.cashbook, name='cashbook'),
    path('save_cash_in/', views_cashbook.save_cash_in, name='save_cash_in'),
    path('save_expense/', views_cashbook.save_expense, name='save_expense'),
    path('save_leakage/', views_cashbook.save_leakage, name='save_leakage'),
    path('expenses-list/', views_cashbook.expenses_list, name='expenses_list'),
    path('edit-expense/<int:pk>/', views_cashbook.edit_expense, name='edit_expense'),
    path('delete-expense/<int:pk>/', views_cashbook.delete_expense, name='delete_expense'),
    path('delete-leakage/<int:pk>/', views_cashbook.delete_leakage, name='delete_leakage'),
    path('save_bank_balance/', views_cashbook.save_bank_balance, name='save_bank_balance'),

    # Stock Dashboard URLs
    path('stock-dashboard/', views_stock_dashboard.stock_dashboard, name='stock_dashboard'),
    path('update-stock/', views_stock_dashboard.update_stock, name='update_stock'),
    path('update-stock/edit/<int:entry_id>/', views_stock_dashboard.edit_stock_entry_view, name='edit_stock_entry'),
    path('update-stock/delete/<int:entry_id>/', views_stock_dashboard.delete_stock_entry_view, name='delete_stock_entry'),
    path('api/stock-data/', views_stock_dashboard.stock_data_api, name='stock_data_api'),

    # Legacy invoice URL (keeping for backward compatibility)
    path('invoice/', views_bills.generate_bill, name='invoice'),

    # Payments Dashboard URL
    path('payments/', views_payments.payments_dashboard, name='payments_dashboard'),
    path('customer-payments/', customer_payments_views.customer_payments, name='customer_payments'),
    path('customer-payments/edit/<int:pk>/', customer_payments_views.edit_customer_payment, name='edit_customer_payment'),
    path('customer-payments/delete/<int:pk>/', customer_payments_views.delete_customer_payment, name='delete_customer_payment'),

    # Companies Dashboard and Company Forms URLs
    path('companies/', views_companies.companies_dashboard, name='companies_dashboard'),
    path('companies/add/', views_companies.add_company, name='add_company'),
    path('companies/edit/<int:company_id>/', views_companies.edit_company, name='edit_company'),

    # User URLs
    path('add-user/', views_users.add_user, name='add_user'),
    path('edit-user/<int:customer_id>/', views_users.add_user, name='edit_user'),
    path('user-data/', views_users.user_data, name='user_data'),
    
    # --------------------------------------------------
    # SUBSCRIPTION DASHBOARD
    # --------------------------------------------------
    path("subscriptions/", subscriptions.subscription_dashboard, name="subscription_dashboard"),

    path("subscriptions/create-plan/", subscriptions.create_subscription_plan, name="create_subscription_plan"),

    path("subscriptions/edit-plan/<int:plan_id>/", subscriptions.edit_subscription_plan, name="edit_subscription_plan"),

    path("subscriptions/plan/<int:plan_id>/add-item/", subscriptions.add_plan_item, name="add_plan_item"),

    path("subscriptions/item/<int:item_id>/update/", subscriptions.update_plan_item, name="update_plan_item"),

    path("subscriptions/item/<int:item_id>/delete/", subscriptions.delete_plan_item, name="delete_plan_item"),

    path("subscriptions/assign/", subscriptions.assign_subscription, name="assign_subscription"),

    path("subscriptions/toggle/<int:subscription_id>/", subscriptions.toggle_subscription, name="toggle_subscription"),

    path("subscriptions/payment/<int:subscription_id>/", subscriptions.record_subscription_payment, name="record_subscription_payment"),

    path("subscriptions/history/", subscriptions.customer_subscription_history, name="customer_subscription_history"),

    path("subscriptions/today-deliveries/", subscriptions.today_deliveries, name="today_deliveries"),
    
    # Admin Orders Dashboard URLs
    path('admin-orders-dashboard/', views_orders_dashboard.admin_orders_dashboard, name='admin_orders_dashboard'),
    path('admin-orders-dashboard/history/', views_orders_dashboard.admin_orders_history, name='admin_orders_history'),
    path('admin-orders-dashboard/customer/<int:customer_id>/history/', views_orders_dashboard.customer_order_history, name='customer_order_history'),
    path('admin-orders-dashboard/orders/<int:order_id>/', views_orders_dashboard.admin_order_detail, name='admin_order_detail'),
    path('admin-orders-dashboard/orders/<int:order_id>/delete/', views_orders_dashboard.delete_order_history_entry, name='delete_order_history_entry'),
    path('admin-delivery-dashboard/', views_orders_dashboard.admin_delivery_dashboard, name='admin_delivery_dashboard'),
    path('confirm-order/<int:order_id>/', views_orders_dashboard.confirm_order, name='confirm_order'),
    path('reject-order/<int:order_id>/', views_orders_dashboard.reject_order, name='reject_order'),
    
   # Offers
    path("offers/", views_offers.offers_dashboard, name="offers_dashboard"),
    path("offers/create/", views_offers.create_offer, name="create_offer"),
    path("offers/update/<int:offer_id>/", views_offers.update_offer, name="update_offer"),
    path("offers/delete/<int:offer_id>/", views_offers.delete_offer, name="delete_offer"),

    # Offer Items
    path("offers/item/add/<int:offer_id>/", views_offers.add_offer_item, name="add_offer_item"),
    path("offers/item/update/<int:item_id>/", views_offers.update_offer_item, name="update_offer_item"),
    path("offers/item/delete/<int:item_id>/", views_offers.delete_offer_item, name="delete_offer_item"),
    
    # Contact Form URL
    path('contact/submit/', views.contact_form_submit, name='contact_form_submit'),
    
    #Payment Gateway Callback URL
    path('users/orders/paytm/callback/', views.payment_callback, name='paytm_callback'),
    path('payment-page/', views.payment_page, name='payment_page'),
    path('payment/initiate/', views.initiate_payment, name='initiate_payment'),
    
]
