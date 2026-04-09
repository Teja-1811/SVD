from django.urls import path

from .views import login_api
from .customer_products import *
from .customer_cataloge import *
from .customer_place_order import *
from .admin_dashboard import *
from .customer_dashboard import *
from .customer_invoice_data import *
from .customer_payment import record_customer_payment
from .customer_contact import (
    api_support_ticket_summary,
    customer_contact_api,
    customer_raised_queries_api,
)
from .admin_enquiry import (
    api_active_enquiries,
    api_resolved_enquiries,
    api_update_enquiry_status,
)
from .customer_offers import *
from .admin_customer import *
from .admin_users import *
from .admin_items import *
from .admin_bills import *
from .admin_cashbook import *
from .admin_payments import *
from .admin_orders_dashboard import *
from .admin_delivery_dashboard import *
from .admin_stock_dashboard import *
from .admin_customer_payments import *
from .admin_companies import *
from .admin_monthly_sales_summary import *
from .admin_category_sales import *
from .admin_subscriptions import *
from .admin_offers import *
from .user_dashboard import *
from .user_offers import *
from .user_subscriptions import subscription_pause_resume_api
from .order_creator import (
    user_create_order,
    user_edit_order,
    user_delete_order,
    user_pending_orders,
)
from .delivery import delivery_today_list
from .delivery import delivery_update
from .payment_gateway import confirm_order_payment_api
from .paytm_webhook import paytm_payment_webhook
from .mobile_push import register_mobile_push_device, unregister_mobile_push_device
from .mobile_payments import mobile_prepare_payment_order, mobile_payment_status

urlpatterns = [
    # Auth / Login
    path('auth/login/', login_api, name='login_api'),

    # Admin Dashboard Counts
    path('dashboard-counts/', dashboard_api, name='dashboard_counts_api'),
    
    #Customer Dashboard APIs
    path('customer-list/', api_customer_list, name='api_customer_list'),
    path('customer-detail/<int:pk>/', api_customer_detail, name='api_customer_detail'),
    path('customer-freeze/<int:pk>/', api_toggle_freeze, name='api_toggle_freeze'),
    path('customer-balance/<int:pk>/', api_update_balance, name='api_update_balance'),
    path('customer-add/', api_add_edit_customer, name='api_add_customer'),
    path('users/', api_user_list, name='api_user_list'),
    path('users/<int:pk>/', api_user_detail, name='api_user_detail'),
    path('users/freeze/<int:pk>/', api_toggle_user_freeze, name='api_toggle_user_freeze'),
    path('users/balance/<int:pk>/', api_update_user_balance, name='api_update_user_balance'),
    path('users/add/', api_add_edit_user, name='api_add_user'),
    
    # Companies APIs
    path('companies/', companies_list_api, name='companies_list_api'),
    path('companies/add/', add_company_api, name='add_company_api'),
    path('companies/edit/<int:company_id>/', edit_company_api, name='edit_company_api'),
    path('companies/items/<int:company_id>/', company_items_api, name='company_items_api'),
    
    
    # Items Management APIs
    path('items/categories/', get_categories, name='get_categories'),
    path('items/by-category/', get_items_by_category, name='get_items_by_category'),
    path('items/add/', add_item, name='add_item'),
    path('items/edit/<int:item_id>/', edit_item, name='edit_item'),
    path('items/freeze-toggle/<int:item_id>/', toggle_freeze_item, name='toggle_freeze_item'),
    
    # Bills Management APIs
    path('bills/list/', api_list_bills, name='api_list_bills'),
    path('bills/create/', api_create_bill, name='api_create_bill'),
    path('bills/<int:bill_id>/', api_bill_detail, name='api_bill_detail'),
    path('bills/<int:bill_id>/items/', api_bill_items, name='api_bill_items'),
    path('bills/<int:bill_id>/download/', api_download_bill, name='api_download_bill'),
    path('bills/<int:bill_id>/delete/', api_delete_bill, name='api_delete_bill'),
    path('bills/<int:bill_id>/edit/', api_edit_bill, name='api_edit_bill'),
    
    #Cashbook Management APIs
    path('cashbook/entries/', api_cashbook_dashboard, name='api_cashbook_entries'),
    path('cashbook/save-cash/', api_save_cash_in, name='api_add_cash_in'),
    path('cashbook/save-bank/', api_save_bank_balance, name='api_add_cash_out'),
    path('cashbook/add-expense/', api_add_expense, name='api_add_expense'),
    path('cashbook/edit-expense/<int:expense_id>/', api_edit_expense, name='api_edit_expense'),
    path('cashbook/expenses/', api_list_expenses, name='api_list_expenses'),
    path('cashbook/delete-expense/<int:expense_id>/', api_delete_expense, name='api_delete_expense'),
    
    #Company Payments APIs
    path('payments/dashboard/', api_payments_dashboard, name='api_payments_dashboard'),
    path('payments/save-daily/', api_save_daily_payments, name='api_save_daily_payment'),
    path('payments/monthly-summary/', api_monthly_payment_summary, name='api_monthly_payment_summary'),
    
    #Admin Orders Dashboard APIs
    path('orders/dashboard/', api_admin_orders_dashboard, name='api_admin_orders_dashboard'),
    path('orders/delivery-dashboard/', api_admin_delivery_dashboard, name='api_admin_delivery_dashboard'),
    path('orders/<int:order_id>/detail/', api_order_detail, name='api_order_detail'),
    path('orders/<int:order_id>/confirm/', api_confirm_order, name='api_confirm_order'),
    path('orders/<int:order_id>/cancel/', api_reject_order, name='api_cancel_order'),
    
    #Admin Stock Dashboard API
    path('stock/dashboard/', stock_dashboard_api, name='stock_dashboard_api'),
    path('stock/update/', update_stock_api, name='update_stock_api'),
    path('stock/entries/<int:entry_id>/edit/', edit_stock_entry_api, name='edit_stock_entry_api'),
    path('stock/entries/<int:entry_id>/delete/', delete_stock_entry_api, name='delete_stock_entry_api'),
    path('stock/leakage/save/', save_leakage_api, name='save_leakage_api'),
    path('stock/leakage/<int:leakage_id>/delete/', delete_leakage_api, name='delete_leakage_api'),
    
    # Monthly Sales Summary API
    path('sales/monthly-summary/', api_monthly_sales_summary, name='api_monthly_sales_summary'),
    path('sales/monthly-summary/pdf/', monthly_summary_pdf_api, name='monthly_summary_pdf_api'),
    path('sales/monthly-summary/update-remaining-due/', update_remaining_due_api, name='update_remaining_due_api'),
    path('sales/category-summary/', api_sales_summary_by_category, name='api_sales_summary_by_category'),
    
    # Subscriptions APIs
    path("subscriptions/dashboard/", api_subscription_dashboard, name="api_subscription_dashboard"),
    path("subscriptions/plans/", api_get_plans, name="api_get_plans"),
    path("subscriptions/create-plan/", api_create_plan, name="api_create_plan"),
    path("subscriptions/edit-plan/<int:plan_id>/", api_edit_plan, name="api_edit_plan"),
    path("subscriptions/plan/<int:plan_id>/add-item/", api_add_plan_item, name="api_add_plan_item"),
    path("subscriptions/item/<int:item_id>/update/", api_update_plan_item, name="api_update_plan_item"),
    path("subscriptions/item/<int:item_id>/delete/", api_delete_plan_item, name="api_delete_plan_item"),
    path("subscriptions/customers/", api_subscription_customers, name="api_subscription_customers"),
    path("subscriptions/assign/", api_assign_subscription, name="api_assign_subscription"),
    path("subscriptions/list/", api_customer_subscriptions, name="api_customer_subscriptions"),
    path("subscriptions/history/", api_customer_subscription_history, name="api_customer_subscription_history"),
    path("subscriptions/toggle/<int:subscription_id>/", api_toggle_subscription, name="api_toggle_subscription"),
    path("subscriptions/payment/<int:subscription_id>/", api_record_subscription_payment, name="api_record_subscription_payment"),
    path("subscriptions/today-deliveries/", api_today_deliveries, name="api_today_deliveries"),

    # Admin offers APIs
    path("offers/dashboard/", api_offers_dashboard, name="api_offers_dashboard"),
    path("offers/create/", api_create_offer, name="api_create_offer"),
    path("offers/update/<int:offer_id>/", api_update_offer, name="api_update_offer"),
    path("offers/delete/<int:offer_id>/", api_delete_offer, name="api_delete_offer"),
    path("offers/item/add/<int:offer_id>/", api_add_offer_item, name="api_add_offer_item"),
    path("offers/item/update/<int:item_id>/", api_update_offer_item, name="api_update_offer_item"),
    path("offers/item/delete/<int:item_id>/", api_delete_offer_item, name="api_delete_offer_item"),
    
    # Customer Payments API
    path('customer-payments/', customer_payments_api, name='customer_payments_api'),
    path('customer-payments/update-status/<int:payment_id>/', update_payment_status_api, name='update_payment_status_api'),
    path('customer-payments/delete/<int:payment_id>/', delete_payment_api, name='delete_payment_api'),
    
    path('admin/enquiries/active/', api_active_enquiries, name='api_active_enquiries'),
    path('admin/enquiries/resolved/', api_resolved_enquiries, name='api_resolved_enquiries'),
    path('admin/enquiries/<int:enquiry_id>/status/', api_update_enquiry_status, name='api_update_enquiry_status'),
    
    
    # Customer Dashboard
    path('customer-dashboard/', customer_dashboard_api, name='customer_dashboard_api'),
    
    # Items APIs
    path('cataloge/', customer_cataloge_api, name='customer_cataloge_api'),
    path('categories/', categories_api, name='categories_api'),
    path('products/', products_api, name='products_api'),
    # Invoice Summary API
    path('customer/invoices/summary/', customer_invoice_summary_api, name='customer_invoice_summary_api'),
    # Place Order API
    path('place-order/', place_order_api, name='place_order_api'),
    path('current-day-orders/', customer_current_day_order_api, name='customer_current_day_order_api'),
    # Invoice List API
    path('customer/invoices/', customer_invoice_list_api, name='customer_invoice_list_api'),
    # Invoice PDF Download API
    path('customer/invoice/download/', customer_invoice_download_api, name='customer_invoice_download_api'),
    # Invoice Details API
    path('customer/invoice/details/', customer_invoice_details_api, name='customer_invoice_details_api'),
    # Customer Payment API
    path('customer/payment/record/', record_customer_payment, name='record_customer_payment'),
    path('contact/', customer_contact_api, name='customer_contact_api'),
    path('enquiries/summary/', api_support_ticket_summary, name='api_support_ticket_summary'),
    path('enquiries/my/', customer_raised_queries_api, name='customer_raised_queries_api'),
    # Customer Offers
    path('customer/offers/', customer_offers, name='customer_offers_api'),
    
    # User APIs
    path('user/dashboard/', user_dashboard_api, name="user_dashboard_api"),
    path('user/offers/', user_offers, name='user_offers_api'),
    path('user/subscriptions/plans/', plans_available_api, name='user_plans_available_api'),
    path('user/subscriptions/current/', current_subscription_api, name='user_current_subscription_api'),
    path('user/subscriptions/history/', subscription_history_api, name='user_subscription_history_api'),
    path('user/subscriptions/pause-resume/', subscription_pause_resume_api, name='user_subscription_pause_resume_api'),
    path('user/profile/', user_profile_update, name='user_profile_update_api'),
    path('user/bills/', user_bills_api, name='user_bills_api'),
    path('user/bills/<int:bill_id>/', user_bill_detail_api, name='user_bill_detail_api'),
    path('user/bills/<int:bill_id>/download/', user_bill_download_api, name='user_bill_download_api'),
    path('user/orders/<int:order_id>/', user_order_detail_api, name='user_order_detail_api'),

    # User orders (create/edit/delete, including prebooking via delivery_date)
    path('user/orders/create/', user_create_order, name='user_create_order'),
    path('user/orders/<int:order_id>/edit/', user_edit_order, name='user_edit_order'),
    path('user/orders/<int:order_id>/delete/', user_delete_order, name='user_delete_order'),
    path('user/orders/pending/', user_pending_orders, name='user_pending_orders'),
    path('payments/orders/confirm/', confirm_order_payment_api, name='confirm_order_payment_api'),
    path('payments/paytm/webhook/', paytm_payment_webhook, name='paytm_payment_webhook'),
    path('mobile/push/register/', register_mobile_push_device, name='register_mobile_push_device'),
    path('mobile/push/unregister/', unregister_mobile_push_device, name='unregister_mobile_push_device'),
    path('mobile/payments/prepare/', mobile_prepare_payment_order, name='mobile_prepare_payment_order'),
    path('mobile/payments/status/<int:order_id>/', mobile_payment_status, name='mobile_payment_status'),
    
    # Delivery agent view (today's pending/completed deliveries for orders + subscriptions)
    path('delivery/today/', delivery_today_list, name='delivery_today_list'),
    path('delivery/update/', delivery_update, name='delivery_update'),
]
