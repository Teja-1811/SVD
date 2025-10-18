from django.shortcuts import render, redirect
from django.db.models import Sum
from .models import Item, DailyPayment, MonthlyPaymentSummary
from datetime import date, timedelta
import calendar


def payments_dashboard(request):
    today = date.today()

    # Read selected year/month from query params or use current month
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    # List all distinct companies from Items table
    companies = Item.objects.values_list('company', flat=True).distinct()

    # --------------------------
    # SAVE DATA (POST request)
    # --------------------------
    if request.method == "POST":
        for company in companies:
            current_day = first_day
            while current_day <= last_day:
                invoice_key = f"invoice_{str(company).lower()}_{current_day}"
                paid_key = f"paid_{str(company).lower()}_{current_day}"
                txn_key = f"txn_{str(company).lower()}_{current_day}"

                invoice_raw = request.POST.get(invoice_key, "").strip()
                paid_raw = request.POST.get(paid_key, "").strip()
                txn_raw = request.POST.get(txn_key, "").strip()

                invoice_val = None if invoice_raw == "" or float(invoice_raw) == 0 else float(invoice_raw)
                paid_val = None if paid_raw == "" or float(paid_raw) == 0 else float(paid_raw)
                txn_val = None if txn_raw == "" else txn_raw

                # Save or update the daily record
                DailyPayment.objects.update_or_create(
                    company=company if company else 'Unknown',
                    date=current_day,
                    defaults={
                        'invoice_amount': invoice_val,
                        'paid_amount': paid_val,
                        'txn_id': txn_val
                    }
                )

                current_day += timedelta(days=1)

        # ✅ Calculate monthly totals AFTER saving daily records
        totals = DailyPayment.objects.filter(
            date__range=(first_day, last_day)
        ).aggregate(
            total_invoice=Sum('invoice_amount'),
            total_paid=Sum('paid_amount')
        )

        grand_total_invoice = totals['total_invoice'] or 0
        grand_total_paid = totals['total_paid'] or 0
        grand_total_due = grand_total_invoice - grand_total_paid

        # Save/update monthly summary
        MonthlyPaymentSummary.objects.update_or_create(
            year=year,
            month=month,
            defaults={
                'total_invoice': grand_total_invoice,
                'total_paid': grand_total_paid,
                'total_due': grand_total_due
            }
        )

        return redirect(request.path + f"?year={year}&month={month}")

    # --------------------------
    # DISPLAY DATA (GET request)
    # --------------------------
    payments = []
    for company in companies:
        daily_records = []
        current_day = first_day
        total_invoice = 0
        total_paid = 0

        while current_day <= last_day:
            record = DailyPayment.objects.filter(company=company, date=current_day).first()
            invoice_amount = record.invoice_amount if record and record.invoice_amount is not None else 0
            paid_amount = record.paid_amount if record and record.paid_amount is not None else 0
            txn_id = record.txn_id if record and record.txn_id else ""

            total_invoice += invoice_amount
            total_paid += paid_amount

            daily_records.append({
                'date': current_day,
                'invoice_amount': invoice_amount,
                'paid_amount': paid_amount,
                'txn_id': txn_id,
            })
            current_day += timedelta(days=1)

        payments.append({
            'company': company if company else 'Unknown',
            'records': daily_records,
            'total_invoice': total_invoice,
            'total_paid': total_paid,
            'remaining_due': total_invoice - total_paid  # ✅ Add this
        })


    # Calculate grand totals for footer display
    grand_total_invoice = sum(p['total_invoice'] for p in payments)
    grand_total_paid = sum(p['total_paid'] for p in payments)
    grand_total_due = grand_total_invoice - grand_total_paid

    # Dropdown year/month options
    years = range(today.year - 5, today.year + 1)
    months = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]

    return render(request, 'milk_agency/dashboards_other/payments_dashboard.html', {
        'payments': payments,
        'selected_year': year,
        'selected_month': month,
        'years': years,
        'months': months,
        'grand_total_invoice': grand_total_invoice,
        'grand_total_paid': grand_total_paid,
        'grand_total_due': grand_total_due
    })
