from decimal import Decimal
from datetime import datetime, date, timedelta
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
    date_str = request.GET.get("date")  # "2026-02"
    customer_id = request.GET.get("customer_id")
    area = request.GET.get("area")

    if not date_str:
        return HttpResponse("date is required (YYYY-MM)", status=400)

    year, month = map(int, date_str.split("-"))
    start_date = datetime(year, month, 1).date()
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day).date()

    customer = Customer.objects.filter(id=customer_id).first()
    if not customer:
        return HttpResponse("Customer not found", status=404)

    # ---------------------------
    # Bills aggregation (CRITICAL)
    # ---------------------------
    bills = Bill.objects.filter(
        customer__retailer_id=customer.retailer_id,
        invoice_date__range=(start_date, end_date)
    ).prefetch_related("items__item").order_by("invoice_date")

    from collections import defaultdict

    aggregated_bills = defaultdict(lambda: {
        "total_amount": Decimal("0"),
        "last_paid": Decimal("0"),
        "op_due_amount": None,
        "items": defaultdict(int),
    })

    for bill in bills:
        date_key = bill.invoice_date.strftime('%Y-%m-%d')

        aggregated_bills[date_key]["total_amount"] += bill.total_amount or 0
        aggregated_bills[date_key]["last_paid"] += bill.last_paid or 0

        if aggregated_bills[date_key]["op_due_amount"] is None:
            aggregated_bills[date_key]["op_due_amount"] = bill.op_due_amount or 0

        for bi in bill.items.all():
            code = bi.item.code
            aggregated_bills[date_key]["items"][code] += bi.quantity or 0

    customer_bills = {}
    customer_items_data = defaultdict(dict)
    unique_codes = set()

    for date_key, data in aggregated_bills.items():
        op_due = data["op_due_amount"] or 0
        customer_bills[date_key] = {
            "invoice_date": datetime.strptime(date_key, "%Y-%m-%d").date(),
            "total_amount": data["total_amount"],
            "paid_amount": data["last_paid"],
            "due_amount": data["total_amount"] - data["last_paid"] + op_due,
        }

        for code, qty in data["items"].items():
            unique_codes.add(code)
            customer_items_data[code][date_key] = qty

    unique_codes = sorted(unique_codes)

    total_quantity_per_item = {
        code: sum(customer_items_data[code].values())
        for code in unique_codes
    }

    # ---------------------------
    # Totals
    # ---------------------------
    total_sales = sum(b["total_amount"] for b in customer_bills.values())
    paid_amount = sum(b["paid_amount"] for b in customer_bills.values())

    opening_due = bills.first().op_due_amount if bills.exists() else customer.due
    due_amount = customer.get_actual_due()

    # ---------------------------
    # Volume + Commission
    # ---------------------------
    milk_volume = Decimal("0")
    curd_volume = Decimal("0")

    for bill in bills:
        for bi in bill.items.all():
            category = (bi.item.category or "").lower()
            qty = bi.quantity or 0
            liters = extract_liters_from_name(bi.item.name) or 0
            total_liters = Decimal(str(liters)) * Decimal(str(qty))

            if category == "milk":
                milk_volume += total_liters
            elif category == "curd":
                curd_volume += total_liters

    days_in_month = calendar.monthrange(year, month)[1]
    avg_milk = milk_volume / days_in_month if milk_volume else Decimal("0")
    avg_curd = curd_volume / days_in_month if curd_volume else Decimal("0")
    avg_volume = avg_milk + avg_curd

    milk_commission = calculate_milk_commission(avg_milk) * days_in_month
    curd_commission = calculate_curd_commission(avg_curd) * days_in_month
    total_commission = milk_commission + curd_commission

    remaining_due = due_amount - total_commission

    date_range = [
        start_date + timedelta(days=i)
        for i in range((end_date - start_date).days + 1)
    ]

    # ---------------------------
    # FINAL CONTEXT (MATCH HTML)
    # ---------------------------
    context = {
        "date": date_str,
        "area": area,
        "selected_date": start_date,
        "selected_customer_obj": customer,
        "start_date": start_date,
        "end_date": end_date,
        "date_range": date_range,
        "customer_bills": customer_bills,
        "customer_items_data": customer_items_data,
        "unique_codes": unique_codes,
        "total_quantity_per_item": total_quantity_per_item,
        "total_sales": total_sales,
        "paid_amount": paid_amount,
        "due_amount": due_amount,
        "milk_volume": avg_milk,
        "curd_volume": avg_curd,
        "avg_volume": avg_volume,
        "milk_commission": milk_commission,
        "curd_commission": curd_commission,
        "total_commission": total_commission,
        "remaining_due": remaining_due,
    }

    pdf = PDFGenerator()
    return pdf.generate_monthly_sales_pdf(context)