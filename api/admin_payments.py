from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.db.models import Sum
from datetime import date, timedelta
import calendar
from decimal import Decimal, InvalidOperation

from milk_agency.models import (
    DailyPayment,
    MonthlyPaymentSummary,
    Company
)


# ======================================================
# 1️⃣ PAYMENTS DASHBOARD (GET)
# ======================================================
@api_view(['GET'])
def api_payments_dashboard(request):
    today = date.today()

    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
    except ValueError:
        return Response({"error": "Invalid year or month"}, status=400)

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    companies = Company.objects.all()

    payments = []
    grand_total_invoice = Decimal("0")
    grand_total_paid = Decimal("0")

    for company in companies:
        daily_records = []
        total_invoice = Decimal("0")
        total_paid = Decimal("0")

        current_day = first_day
        while current_day <= last_day:
            record = DailyPayment.objects.filter(
                company=company,
                date=current_day
            ).first()

            invoice_amount = record.invoice_amount if record and record.invoice_amount else Decimal("0")
            paid_amount = record.paid_amount if record and record.paid_amount else Decimal("0")

            total_invoice += invoice_amount
            total_paid += paid_amount

            daily_records.append({
                "date": str(current_day),
                "invoice_amount": float(invoice_amount),
                "paid_amount": float(paid_amount)
            })

            current_day += timedelta(days=1)

        grand_total_invoice += total_invoice
        grand_total_paid += total_paid

        payments.append({
            "company_id": company.id,
            "company_name": company.name,
            "records": daily_records,
            "total_invoice": float(total_invoice),
            "total_paid": float(total_paid),
            "remaining_due": float(total_invoice - total_paid)
        })

    grand_total_due = grand_total_invoice - grand_total_paid

    return Response({
        "year": year,
        "month": month,
        "payments": payments,
        "grand_total_invoice": float(grand_total_invoice),
        "grand_total_paid": float(grand_total_paid),
        "grand_total_due": float(grand_total_due)
    })


# ======================================================
# 2️⃣ SAVE DAILY PAYMENTS (POST)
# ======================================================
@api_view(['POST'])
def api_save_daily_payments(request):

    try:
        year = int(request.data.get("year"))
        month = int(request.data.get("month"))
    except (TypeError, ValueError):
        return Response({"error": "year and month are required"}, status=400)

    data = request.data.get("data", {})

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    companies = Company.objects.all()

    for company in companies:
        company_data = data.get(str(company.id), {})

        current_day = first_day
        while current_day <= last_day:

            day_data = company_data.get(str(current_day), {})
            invoice_val = day_data.get("invoice")
            paid_val = day_data.get("paid")

            # Correct zero handling
            try:
                invoice_val = Decimal(str(invoice_val)) if invoice_val is not None else None
            except (InvalidOperation, TypeError):
                invoice_val = None

            try:
                paid_val = Decimal(str(paid_val)) if paid_val is not None else None
            except (InvalidOperation, TypeError):
                paid_val = None

            DailyPayment.objects.update_or_create(
                company=company,
                date=current_day,
                defaults={
                    "invoice_amount": invoice_val,
                    "paid_amount": paid_val
                }
            )

            current_day += timedelta(days=1)

    # -------- Monthly summary --------
    totals = DailyPayment.objects.filter(
        date__year=year,
        date__month=month
    ).aggregate(
        total_invoice=Sum("invoice_amount"),
        total_paid=Sum("paid_amount")
    )

    total_invoice = totals["total_invoice"] or Decimal("0")
    total_paid = totals["total_paid"] or Decimal("0")
    total_due = total_invoice - total_paid

    MonthlyPaymentSummary.objects.update_or_create(
        year=year,
        month=month,
        defaults={
            "total_invoice": total_invoice,
            "total_paid": total_paid,
            "total_due": total_due
        }
    )

    return Response({"success": True})


# ======================================================
# 3️⃣ MONTHLY SUMMARY (FOOTER / REPORT)
# ======================================================
@api_view(['GET'])
def api_monthly_payment_summary(request):

    try:
        year = int(request.GET.get("year"))
        month = int(request.GET.get("month"))
    except (TypeError, ValueError):
        return Response({"error": "year and month are required"}, status=400)

    summary = MonthlyPaymentSummary.objects.filter(
        year=year,
        month=month
    ).first()

    if not summary:
        return Response({
            "total_invoice": 0,
            "total_paid": 0,
            "total_due": 0
        })

    return Response({
        "total_invoice": float(summary.total_invoice),
        "total_paid": float(summary.total_paid),
        "total_due": float(summary.total_due)
    })
