from django.shortcuts import render
from urllib.parse import quote
from django.db.models import Sum, F, Case, When, Value, IntegerField
from django.db import transaction
from django.utils import timezone
from itertools import groupby
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Bill, Customer, Item, CashbookEntry, CustomerMonthlyCommission, Contact
from .push_notifications import notify_admin_enquiry_created
from datetime import datetime
import json
from customer_portal.models import CustomerOrder


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

    unresolved_queries_count = Contact.objects.filter(status="active").count()
    pending_orders_count = CustomerOrder.objects.filter(status="pending").count()

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
        "unresolved_queries_count": unresolved_queries_count,
        "pending_orders_count": pending_orders_count,
    }

    return render(request, "milk_agency/home/home_dashboard.html", context)


# =========================================================
# CONTACT FORM SUBMIT
# =========================================================
def contact_form_submit(request):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            email = request.POST.get('email', '').strip()
            subject = request.POST.get('subject', '').strip()
            message = request.POST.get('message', '').strip()

            if not all([name, phone, subject, message]):
                if is_ajax:
                    return JsonResponse({'success': False, 'message': 'Please fill all required fields.'})
                messages.error(request, 'Please fill all required fields.')
                return redirect('/#contact')

            contact = Contact.objects.create(
                name=name,
                phone=phone,
                email=email if email else None,
                subject=subject,
                message=message
            )
            transaction.on_commit(lambda contact_id=contact.id: notify_admin_enquiry_created(Contact.objects.get(pk=contact_id)))

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

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': 'Thank you! We will contact you soon.',
                    'whatsapp_url': whatsapp_url
                })

            messages.success(request, 'Thank you! We will contact you soon.')
            return redirect('/#contact')

        except Exception as exc:
            if is_ajax:
                return JsonResponse({'success': False, 'message': f'Server error. Try again. ({exc})'})
            messages.error(request, f'Server error. Try again. ({exc})')
            return redirect('/#contact')

    if is_ajax:
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})
    return redirect('/#contact')


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


@login_required
@never_cache
def admin_enquiries(request):
    if request.method == "POST":
        enquiry_id = request.POST.get("enquiry_id")
        new_status = (request.POST.get("status") or "").strip().lower()
        enquiry = get_object_or_404(Contact, id=enquiry_id)

        allowed_statuses = {choice[0] for choice in Contact.STATUS_CHOICES}
        if new_status not in allowed_statuses:
            messages.error(request, "Invalid enquiry status.")
            return redirect("milk_agency:admin_enquiries")

        enquiry.status = new_status
        enquiry.save(update_fields=["status"])
        messages.success(request, "Enquiry status updated successfully.")
        return redirect("milk_agency:admin_enquiries")

    active_enquiries = Contact.objects.filter(status="active").order_by("-created_at")
    resolved_enquiries = Contact.objects.filter(status="resolved").order_by("-created_at")

    return render(
        request,
        "milk_agency/home/enquiries.html",
        {
            "active_enquiries": active_enquiries,
            "resolved_enquiries": resolved_enquiries,
            "unresolved_queries_count": active_enquiries.count(),
        },
    )


# views.py

from django.shortcuts import render
from django.conf import settings
import uuid
from .utils import generate_checksum
from paytmchecksum import PaytmChecksum
import requests

def payment_page(request):
    return render(request, "payments_form.html")

def initiate_payment(request):
    if request.method == "POST":
        import uuid

        order_id = str(uuid.uuid4()).replace("-", "")[:20]
        amount = "1.00"

        paytmParams = {
            "body": {
                "requestType": "Payment",
                "mid": settings.PAYTM_MID,
                "websiteName": "DEFAULT",
                "orderId": order_id,
                "callbackUrl": settings.PAYTM_CALLBACK_URL,
                "txnAmount": {
                    "value": amount,
                    "currency": "INR",
                },
                "userInfo": {
                    "custId": "CUST_001",
                },
            }
        }

        checksum = PaytmChecksum.generateSignature(
            json.dumps(paytmParams["body"]),
            settings.PAYTM_MERCHANT_KEY
        )

        paytmParams["head"] = {
            "signature": checksum
        }

        url = f"https://securegw.paytm.in/theia/api/v1/initiateTransaction?mid={settings.PAYTM_MID}&orderId={order_id}"

        response = requests.post(url, json=paytmParams)
        response_data = response.json()

        print("PAYTM RESPONSE:", response_data)

        # SAFE ACCESS
        if "body" in response_data and "txnToken" in response_data["body"]:
            txnToken = response_data["body"]["txnToken"]
        else:
            return HttpResponse(f"Paytm Error: {response_data}")

        return render(request, "paytm_checkout.html", {
            "txnToken": txnToken,
            "order_id": order_id,
            "mid": settings.PAYTM_MID
        })
    
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def payment_callback(request):
    if request.method == "POST":
        data = request.POST.dict()
        print("PAYTM RESPONSE:", data)

        if data.get("STATUS") == "TXN_SUCCESS":
            return HttpResponse("Payment Success")
        else:
            return HttpResponse("Payment Failed")

    return HttpResponse("Invalid request")