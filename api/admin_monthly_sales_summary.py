from decimal import Decimal
from datetime import datetime, date
import calendar

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Sum, F
from django.db.models.functions import Coalesce

from milk_agency.models import (
    Customer, Bill, DailySalesSummary
)
from milk_agency.views_sales_summary import extract_liters_from_name
from milk_agency.monthly_sales_summary import (
    calculate_milk_commission,
    calculate_curd_commission
)

from milk_agency.monthly_sales_pdf_utils import MonthlySalesPDFGenerator as PDFGenerator

@api_view(['GET'])
def api_monthly_sales_summary(request):
    """
    API-1: Monthly Sales Summary for Android
    Params:
      ?date=YYYY-MM   (e.g. 2026-02)
      ?customer_id=ID (optional)
    """

    selected_month = request.GET.get('date', datetime.now().strftime('%Y-%m'))
    customer_id = request.GET.get('customer_id')

    # ---- Parse year & month safely ----
    try:
        year, month = map(int, selected_month[:7].split('-'))
    except:
        year, month = datetime.now().year, datetime.now().month

    days_in_month = calendar.monthrange(year, month)[1]

    # ---- If customer selected ----
    customer = None
    bills = Bill.objects.none()
    sales_data = DailySalesSummary.objects.filter(
        date__year=year, date__month=month
    )

    if customer_id:
        customer = Customer.objects.filter(id=customer_id).first()
        if customer:
            bills = Bill.objects.filter(
                customer__retailer_id=customer.retailer_id,
                invoice_date__year=year,
                invoice_date__month=month
            ).order_by('invoice_date')

            sales_data = DailySalesSummary.objects.filter(
                date__year=year,
                date__month=month,
                retailer_id=customer.retailer_id
            )

    # ---- Totals from Bills ----
    invoice_total = bills.aggregate(
        total=Coalesce(Sum('total_amount'), Decimal('0.00'))
    )['total']

    paid_total = bills.aggregate(
        total=Coalesce(Sum('last_paid'), Decimal('0.00'))
    )['total']

    opening_due = bills.first().op_due_amount if bills.exists() else (customer.due if customer else Decimal('0'))

    due_total = opening_due + invoice_total - paid_total

    # ---- Total items sold ----
    total_items = 0
    for sale in sales_data:
        try:
            items = sale.get_item_list()
            total_items += sum(item['quantity'] for item in items)
        except:
            pass

    # ---- Volume calculation (Milk & Curd) ----
    milk_volume = Decimal('0')
    curd_volume = Decimal('0')

    if customer:
        bill_qs = Bill.objects.filter(
            customer__retailer_id=customer.retailer_id,
            invoice_date__year=year,
            invoice_date__month=month
        ).prefetch_related('items__item')

        for bill in bill_qs:
            for bill_item in bill.items.all():
                category = (bill_item.item.category or "").lower()
                quantity = bill_item.quantity or 0
                liters_per_unit = extract_liters_from_name(bill_item.item.name) or 0

                total_liters = Decimal(str(liters_per_unit)) * Decimal(str(quantity))

                if category == "milk":
                    milk_volume += total_liters
                elif category == "curd":
                    curd_volume += total_liters

    total_volume = milk_volume + curd_volume

    # ---- Average per day ----
    avg_milk = (milk_volume / days_in_month) if milk_volume > 0 else Decimal('0')
    avg_curd = (curd_volume / days_in_month) if curd_volume > 0 else Decimal('0')
    avg_volume = avg_milk + avg_curd

    # ---- Commission ----
    milk_commission = calculate_milk_commission(avg_milk) * days_in_month
    curd_commission = calculate_curd_commission(avg_curd) * days_in_month
    total_commission = milk_commission + curd_commission

    remaining_due = due_total - total_commission if total_commission > 0 else due_total

    return Response({
        "year": year,
        "month": month,
        "days_in_month": days_in_month,

        "customer": {
            "id": customer.id if customer else None,
            "name": customer.name if customer else None,
            "phone": customer.phone if customer else None,
        },

        "summary": {
            "total_sales": float(invoice_total),
            "paid_amount": float(paid_total),
            "opening_due": float(opening_due),
            "due_amount": float(due_total),
            "remaining_due": float(remaining_due),
            "total_items": total_items,
        },

        "volume": {
            "milk_volume": float(milk_volume),
            "curd_volume": float(curd_volume),
            "total_volume": float(total_volume),
            "avg_milk_per_day": float(avg_milk),
            "avg_curd_per_day": float(avg_curd),
            "avg_total_per_day": float(avg_volume),
        },

        "commission": {
            "milk_commission": float(milk_commission),
            "curd_commission": float(curd_commission),
            "total_commission": float(total_commission),
        }
    })

@api_view(["GET"])
def monthly_summary_pdf_api(request):
    date_str = request.GET.get("date")  # "2026-01"
    customer_id = request.GET.get("customer_id")
    area = request.GET.get("area")

    if not date_str or not customer_id:
        return HttpResponse("date and customer_id are required", status=400)

    # --- Convert YYYY-MM to start & end date ---
    year, month = map(int, date_str.split("-"))
    start_date = datetime(year, month, 1).date()
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day).date()

    # --- Fetch customer ---
    selected_customer = Customer.objects.filter(id=customer_id).first()
    if not selected_customer:
        return HttpResponse("Customer not found", status=404)

    # --- Fetch bills (IMPORTANT: use invoice_date) ---
    customer_bills = Bill.objects.filter(
        customer__retailer_id=selected_customer.retailer_id,
        invoice_date__range=(start_date, end_date)
    ).order_by("invoice_date")

    # --- Fetch daily summaries (use retailer_id, not customer FK) ---
    summaries = DailySalesSummary.objects.filter(
        retailer_id=selected_customer.retailer_id,
        date__range=(start_date, end_date)
    ).select_related("item")

    # --- Build item-wise structure ---
    customer_items_data = {}
    unique_codes = set()

    for s in summaries:
        code = s.item.code
        unique_codes.add(code)

        if code not in customer_items_data:
            customer_items_data[code] = {
                "total_qty": 0,
                "total_amount": 0,
                "price": s.item.selling_price,
            }

        customer_items_data[code]["total_qty"] += s.quantity
        customer_items_data[code]["total_amount"] += s.amount

    unique_codes = sorted(unique_codes)

    # --- Totals ---
    total_quantity_per_item = {
        code: data["total_qty"] for code, data in customer_items_data.items()
    }

    total_amount_per_item = {
        code: data["total_amount"] for code, data in customer_items_data.items()
    }

    total_amount = sum(total_amount_per_item.values())

    # --- FINAL context for PDF ---
    context = {
        "date": date_str,
        "customer_id": customer_id,
        "area": area,
        "selected_customer_obj": selected_customer,
        "start_date": start_date,
        "end_date": end_date,
        "customer_bills": customer_bills,
        "customer_items_data": customer_items_data,
        "unique_codes": unique_codes,
        "total_quantity_per_item": total_quantity_per_item,
        "total_amount_per_item": total_amount_per_item,
        "total_amount": total_amount,
    }

    pdf = PDFGenerator()
    return pdf.generate_monthly_sales_pdf(context)
