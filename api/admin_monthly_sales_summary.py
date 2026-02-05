from datetime import datetime, date, timedelta
from decimal import Decimal
import calendar
import json
from collections import defaultdict

from django.http import JsonResponse
from django.db.models import Sum, F
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from milk_agency.models import DailySalesSummary, Customer, Bill, CustomerMonthlyCommission
from milk_agency.views_sales_summary import extract_liters_from_name
from milk_agency.monthly_sales_pdf_utils import MonthlySalesPDFGenerator


# -------------------------------------------------------
# COMMISSION CALCULATIONS (UNCHANGED)
# -------------------------------------------------------

def calculate_milk_commission(volume):
    volume = Decimal(str(volume))
    if volume <= 15:
        return volume * Decimal('0.2')
    elif volume <= 30:
        return Decimal('15') * Decimal('0.25') + (volume - Decimal('15')) * Decimal('0.3')
    else:
        return Decimal('15') * Decimal('0.3') + Decimal('15') * Decimal('0.3') + (volume - Decimal('30')) * Decimal('0.35')


def calculate_curd_commission(volume):
    volume = Decimal(str(volume))
    if volume <= 20:
        return volume * Decimal('0.25')
    elif volume <= 35:
        return Decimal('20') * Decimal('0.25') + (volume - Decimal('20')) * Decimal('0.35')
    else:
        return Decimal('20') * Decimal('0.25') + Decimal('15') * Decimal('0.35') + (volume - Decimal('35')) * Decimal('0.5')


# ==========================================================
# 1️⃣ MONTHLY SALES SUMMARY API (FOR ANDROID)
# ==========================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monthly_sales_summary_api(request):
    selected_month = request.GET.get('date', datetime.now().strftime('%Y-%m'))
    selected_area = request.GET.get('area', '')
    selected_customer = request.GET.get('customer', '')

    try:
        year, month = map(int, selected_month.split('-'))
    except:
        year = datetime.now().year
        month = datetime.now().month

    # ---- Areas list ----
    areas = list(
        Customer.objects.exclude(area__exact='')
        .values_list('area', flat=True)
        .distinct()
        .order_by('area')
    )

    # ---- Customers ----
    if selected_area:
        customers = list(Customer.objects.filter(area=selected_area).values("id", "name"))
    else:
        customers = list(Customer.objects.all().values("id", "name"))

    # ---- Sales data ----
    if selected_customer:
        customer = get_object_or_404(Customer, id=selected_customer)
        sales_data = DailySalesSummary.objects.filter(
            date__year=year,
            date__month=month,
            retailer_id=customer.retailer_id
        )
    else:
        sales_data = DailySalesSummary.objects.filter(
            date__year=year,
            date__month=month
        )
        customer = None

    # ---- Paid & Due ----
    paid_amount = 0
    due_total = 0
    total_sales = 0

    if customer:
        bills = Bill.objects.filter(
            customer__retailer_id=customer.retailer_id,
            invoice_date__year=year,
            invoice_date__month=month,
        )

        invoice_total = bills.aggregate(total=Sum('total_amount'))['total'] or 0
        paid_total = bills.aggregate(total=Sum('last_paid'))['total'] or 0
        opening_due = bills.first().op_due_amount if bills.exists() else customer.due

        due_total = opening_due + invoice_total - paid_total

        paid_amount = paid_total
        total_sales = invoice_total

    # ---- Total Items ----
    total_items = 0
    for sale in sales_data:
        try:
            items = sale.get_item_list()
            total_items += sum(item['quantity'] for item in items)
        except:
            pass

    # ---- Volume Calculation ----
    milk_volume = Decimal('0')
    curd_volume = Decimal('0')

    if customer:
        bills = Bill.objects.filter(
            customer__retailer_id=customer.retailer_id,
            invoice_date__year=year,
            invoice_date__month=month,
        ).prefetch_related('items__item')

        for bill in bills:
            for bill_item in bill.items.all():
                category = (bill_item.item.category or "").lower()
                liters_per_unit = extract_liters_from_name(bill_item.item.name)
                total_liters = Decimal(str(liters_per_unit)) * Decimal(str(bill_item.quantity))

                if category == "milk":
                    milk_volume += total_liters
                elif category == "curd":
                    curd_volume += total_liters

    days_in_month = calendar.monthrange(year, month)[1]

    avg_milk = milk_volume / days_in_month if milk_volume else Decimal('0')
    avg_curd = curd_volume / days_in_month if curd_volume else Decimal('0')
    avg_volume = avg_milk + avg_curd

    milk_commission = calculate_milk_commission(avg_milk) * days_in_month
    curd_commission = calculate_curd_commission(avg_curd) * days_in_month
    total_commission = milk_commission + curd_commission

    response = {
        "year": year,
        "month": month,
        "areas": areas,
        "customers": customers,
        "selected_customer": selected_customer,
        "total_sales": float(total_sales),
        "paid_amount": float(paid_amount),
        "due_amount": float(due_total),
        "total_items": total_items,
        "milk_volume": float(avg_milk),
        "curd_volume": float(avg_curd),
        "avg_volume": float(avg_volume),
        "milk_commission": float(milk_commission),
        "curd_commission": float(curd_commission),
        "total_commission": float(total_commission),
        "remaining_due": float(due_total - total_commission if total_commission else due_total),
    }

    return JsonResponse(response)


# ==========================================================
# 2️⃣ GENERATE MONTHLY SALES PDF (ANDROID DOWNLOAD)
# ==========================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def generate_monthly_sales_pdf_api(request):
    pdf_generator = MonthlySalesPDFGenerator()
    return pdf_generator.generate_monthly_sales_pdf(request.GET, request)


# ==========================================================
# 3️⃣ UPDATE REMAINING DUE + SAVE COMMISSION
# ==========================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_remaining_due_api(request):

    customer_id = request.data.get("customer_id")
    remaining_due = request.data.get("remaining_due")
    selected_month = request.data.get("selected_month")
    commission_data = request.data.get("commission_data")

    customer = get_object_or_404(Customer, id=customer_id)

    customer.due = Decimal(str(remaining_due))
    customer.save()

    if selected_month and commission_data:
        year, month = map(int, selected_month.split('-'))

        CustomerMonthlyCommission.objects.update_or_create(
            customer=customer,
            year=year,
            month=month,
            defaults={
                "milk_volume": commission_data.get("milk_volume", 0),
                "curd_volume": commission_data.get("curd_volume", 0),
                "total_volume": commission_data.get("avg_volume", 0),
                "milk_commission_rate": commission_data.get("milk_commission_rate", 0),
                "curd_commission_rate": commission_data.get("curd_commission_rate", 0),
                "commission_amount": commission_data.get("total_commission", 0),
            }
        )

    return JsonResponse({
        "status": "success",
        "message": f"Customer balance updated to ₹{remaining_due}"
    })
