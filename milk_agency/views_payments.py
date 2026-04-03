import calendar
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from .models import Company, DailyPayment
from .utils import refresh_monthly_payment_summary


def _parse_optional_decimal(value):
    value = (value or "").strip()
    if not value:
        return None

    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None


@login_required
def payments_dashboard(request):
    today = date.today()

    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    companies = list(Company.objects.all())
    month_payments = DailyPayment.objects.filter(
        date__range=(first_day, last_day)
    ).select_related("company")
    payment_map = {
        (payment.company_id, payment.date): payment
        for payment in month_payments
    }

    if request.method == "POST":
        to_create = []
        to_update = []
        delete_ids = []

        with transaction.atomic():
            for company in companies:
                current_day = first_day
                while current_day <= last_day:
                    date_str = current_day.strftime("%Y-%m-%d")
                    invoice_key = f"invoice_{company.id}_{date_str}"
                    paid_key = f"paid_{company.id}_{date_str}"

                    invoice_val = _parse_optional_decimal(request.POST.get(invoice_key))
                    paid_val = _parse_optional_decimal(request.POST.get(paid_key))
                    existing = payment_map.get((company.id, current_day))

                    if invoice_val is None and paid_val is None:
                        if existing:
                            delete_ids.append(existing.id)
                        current_day += timedelta(days=1)
                        continue

                    if existing:
                        if (
                            existing.invoice_amount != invoice_val
                            or existing.paid_amount != paid_val
                        ):
                            existing.invoice_amount = invoice_val
                            existing.paid_amount = paid_val
                            to_update.append(existing)
                    else:
                        to_create.append(
                            DailyPayment(
                                company=company,
                                date=current_day,
                                invoice_amount=invoice_val,
                                paid_amount=paid_val,
                            )
                        )

                    current_day += timedelta(days=1)

            if delete_ids:
                DailyPayment.objects.filter(id__in=delete_ids).delete()
            if to_create:
                DailyPayment.objects.bulk_create(to_create)
            if to_update:
                DailyPayment.objects.bulk_update(
                    to_update,
                    ["invoice_amount", "paid_amount", "updated_at"],
                )

            refresh_monthly_payment_summary(first_day)

        return redirect(request.path + f"?year={year}&month={month}")

    payments = []
    for company in companies:
        daily_records = []
        current_day = first_day
        total_invoice = Decimal("0")
        total_paid = Decimal("0")

        while current_day <= last_day:
            record = payment_map.get((company.id, current_day))
            invoice_amount = (
                record.invoice_amount
                if record and record.invoice_amount is not None
                else Decimal("0")
            )
            paid_amount = (
                record.paid_amount
                if record and record.paid_amount is not None
                else Decimal("0")
            )

            total_invoice += invoice_amount
            total_paid += paid_amount
            daily_records.append(
                {
                    "date": current_day,
                    "invoice_amount": invoice_amount,
                    "paid_amount": paid_amount,
                }
            )
            current_day += timedelta(days=1)

        payments.append(
            {
                "company": company,
                "records": daily_records,
                "total_invoice": total_invoice,
                "total_paid": total_paid,
                "remaining_due": total_invoice - total_paid,
            }
        )

    grand_total_invoice = sum(
        (payment["total_invoice"] for payment in payments),
        Decimal("0"),
    )
    grand_total_paid = sum(
        (payment["total_paid"] for payment in payments),
        Decimal("0"),
    )
    grand_total_due = grand_total_invoice - grand_total_paid

    years = range(today.year - 5, today.year + 1)
    months = [
        (1, "January"),
        (2, "February"),
        (3, "March"),
        (4, "April"),
        (5, "May"),
        (6, "June"),
        (7, "July"),
        (8, "August"),
        (9, "September"),
        (10, "October"),
        (11, "November"),
        (12, "December"),
    ]

    return render(
        request,
        "milk_agency/dashboards_other/payments_dashboard.html",
        {
            "payments": payments,
            "selected_year": year,
            "selected_month": month,
            "years": years,
            "months": months,
            "grand_total_invoice": grand_total_invoice,
            "grand_total_paid": grand_total_paid,
            "grand_total_due": grand_total_due,
        },
    )
