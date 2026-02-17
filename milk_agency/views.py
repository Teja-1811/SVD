from django.shortcuts import render
from urllib.parse import quote
from django.db.models import Sum, F, Case, When, Value, IntegerField
from django.utils import timezone
from itertools import groupby
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from .models import Bill, Customer, Item, CashbookEntry, CustomerMonthlyCommission, Contact
from datetime import datetime
import json


# =========================================================
# HOME DASHBOARD
# =========================================================
@login_required
@never_cache
def home(request):
    company_filter = request.GET.get('company')
    category_filter = request.GET.get('category')

    today = timezone.now().date()

    # -----------------------------------------------------
    # AUTO COMMISSION CALCULATION (RUN ONCE SAFELY)
    # -----------------------------------------------------
    if today.day == 5:
        previous_month = today.month - 1 if today.month > 1 else 12
        previous_year = today.year if today.month > 1 else today.year - 1

        commission_exists = CustomerMonthlyCommission.objects.filter(
            year=previous_year,
            month=previous_month
        ).exists()

        if not commission_exists:
            from .utils import calculate_monthly_commissions
            calculate_monthly_commissions(previous_year, previous_month)

    # -----------------------------------------------------
    # TODAY SALES
    # -----------------------------------------------------
    today_bills = Bill.objects.filter(invoice_date=today)
    today_sales = today_bills.aggregate(total=Sum("total_amount"))["total"] or 0
    today_bills_count = today_bills.count()

    # -----------------------------------------------------
    # CUSTOMER DUES
    # -----------------------------------------------------
    total_due = Customer.objects.aggregate(total=Sum("due"))["total"] or 0

    # -----------------------------------------------------
    # CASH-IN TODAY (FULL DENOMINATIONS)
    # -----------------------------------------------------
    cash_entry = CashbookEntry.objects.first()
    if cash_entry:
        today_cash_in = (
            cash_entry.c500 * 500 +
            cash_entry.c200 * 200 +
            cash_entry.c100 * 100 +
            cash_entry.c50 * 50 +
            cash_entry.c20 * 20 +
            cash_entry.c10 * 10 +
            cash_entry.coin20 * 20 +
            cash_entry.coin10 * 10 +
            cash_entry.coin5 * 5 +
            cash_entry.coin2 * 2 +
            cash_entry.coin1 * 1
        )
    else:
        today_cash_in = 0

    # -----------------------------------------------------
    # STOCK SUMMARY
    # -----------------------------------------------------
    total_stock_value = (
        Item.objects.aggregate(total=Sum(F("stock_quantity") * F("buying_price")))["total"]
        or 0
    )

    total_stock_items = Item.objects.filter(frozen=False).count()
    low_stock_items = Item.objects.filter(stock_quantity__lt=F("pcs_count")).count()
    out_of_stock_items = Item.objects.filter(stock_quantity=0).count()

    # -----------------------------------------------------
    # ALL STOCK ITEMS WITH COMPUTED FIELDS
    # -----------------------------------------------------
    all_stock_items = (
        Item.objects.filter(frozen=False)
        .annotate(
            crates=F("stock_quantity") / F("pcs_count"),
            packets=F("stock_quantity") % F("pcs_count"),
            stock_value=F("stock_quantity") * F("buying_price"),
            category_priority=Case(
                When(category__iexact="milk", then=Value(1)),
                When(category__iexact="curd", then=Value(2)),
                When(category__iexact="buckets", then=Value(3)),
                When(category__iexact="panner", then=Value(4)),
                When(category__iexact="sweets", then=Value(5)),
                When(category__iexact="flavoured milk", then=Value(6)),
                When(category__iexact="ghee", then=Value(7)),
                When(category__iexact="cups", then=Value(8)),
                default=Value(9),
                output_field=IntegerField(),
            ),
        )
        .order_by("company__name", "category_priority", "name")
    )

    # -----------------------------------------------------
    # APPLY FILTERS
    # -----------------------------------------------------
    if company_filter:
        all_stock_items = all_stock_items.filter(company__name__iexact=company_filter)

    if category_filter:
        all_stock_items = all_stock_items.filter(category__iexact=category_filter)

    # -----------------------------------------------------
    # GROUP STOCK BY COMPANY
    # -----------------------------------------------------
    stock_by_company = {}
    for company, items in groupby(
        all_stock_items,
        key=lambda x: x.company.name if x.company else "No Company"
    ):
        stock_by_company[company] = list(items)

    # -----------------------------------------------------
    # DROPDOWN VALUES
    # -----------------------------------------------------
    companies = (
        Item.objects.filter(frozen=False, company__isnull=False)
        .values_list("company__name", flat=True)
        .distinct()
    )

    categories = (
        Item.objects.filter(frozen=False)
        .exclude(category__isnull=True)
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
    )

    context = {
        "companies": companies,
        "categories": categories,
        "current_date": today.strftime("%d-%m-%Y"),
        "today_sales": today_sales,
        "total_due": total_due,
        "today_bills": today_bills_count,
        "today_cash_in": today_cash_in,
        "total_stock_items": total_stock_items,
        "total_stock_value": total_stock_value,
        "low_stock_items": low_stock_items,
        "out_of_stock_items": out_of_stock_items,
        "stock_by_company": stock_by_company,
        "today_top_items": None,
        "today_active_customers": None,
        "today_bills_list": None,
    }

    return render(request, "milk_agency/home/home_dashboard.html", context)


# =========================================================
# CONTACT FORM SUBMIT
# =========================================================
def contact_form_submit(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            email = request.POST.get('email', '').strip()
            subject = request.POST.get('subject', '').strip()
            message = request.POST.get('message', '').strip()

            if not all([name, phone, subject, message]):
                return JsonResponse({'success': False, 'message': 'Please fill all required fields.'})

            Contact.objects.create(
                name=name,
                phone=phone,
                email=email if email else None,
                subject=subject,
                message=message
            )

            whatsapp_message = f"""
New Contact Form Inquiry - SVD Milk Agencies

Name: {name}
Phone: {phone}
Email: {email if email else 'N/A'}
Subject: {subject}

Message:
{message}
"""

            encoded_message = quote(whatsapp_message)
            whatsapp_url = f"https://wa.me/919392890375?text={encoded_message}"

            return JsonResponse({
                'success': True,
                'message': 'Thank you! We will contact you soon.',
                'whatsapp_url': whatsapp_url
            })

        except Exception:
            return JsonResponse({'success': False, 'message': 'Server error. Try again.'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


# STATIC PAGES
def about(request):
    return render(request, "about.html")

def contact(request):
    return render(request, "contact_us.html")

def privacy(request):
    return render(request, "privacy.html")

def terms(request):
    return render(request, "terms.html")

def refund(request):
    return render(request, "refund.html")

def checkout(request):
    return render(request, "checkout.html")
