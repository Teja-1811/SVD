from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max, F, ExpressionWrapper, DecimalField, Count
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import (
    CashbookEntry, Expense, BankBalance,
    MonthlyPaymentSummary, DailyPayment,
    Customer, Bill, Item, Company
)


# -------------------------------------------------------
# CASHBOOK DASHBOARD
# -------------------------------------------------------
@login_required
def cashbook(request):
    today = timezone.now().date()

    months = [
        (1, "January"), (2, "February"), (3, "March"),
        (4, "April"), (5, "May"), (6, "June"),
        (7, "July"), (8, "August"), (9, "September"),
        (10, "October"), (11, "November"), (12, "December"),
    ]
    years = list(range(today.year - 5, today.year + 2))

    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))

    # ---------------- CASH ENTRY ----------------
    cash_entry = CashbookEntry.objects.first() or CashbookEntry.objects.create()

    total_cash_in = (
        cash_entry.c500 * 500 + cash_entry.c200 * 200 +
        cash_entry.c100 * 100 + cash_entry.c50 * 50 +
        cash_entry.c20 * 20 + cash_entry.c10 * 10 +
        cash_entry.coin20 * 20 + cash_entry.coin10 * 10 +
        cash_entry.coin5 * 5 + cash_entry.coin2 * 2 +
        cash_entry.coin1 * 1
    )

    denomination_totals = {
        'c500': cash_entry.c500 * 500,
        'c200': cash_entry.c200 * 200,
        'c100': cash_entry.c100 * 100,
        'c50': cash_entry.c50 * 50,
        'c20': cash_entry.c20 * 20,
        'c10': cash_entry.c10 * 10,
        'coin20': cash_entry.coin20 * 20,
        'coin10': cash_entry.coin10 * 10,
        'coin5': cash_entry.coin5 * 5,
        'coin2': cash_entry.coin2 * 2,
        'coin1': cash_entry.coin1 * 1,
    }

    # ---------------- EXPENSES ----------------
    cash_out_entries = Expense.objects.filter(
        date__year=selected_year,
        date__month=selected_month
    ).order_by('-created_at')

    total_cash_out = cash_out_entries.aggregate(total=Sum('amount'))['total'] or 0

    # ---------------- BANK BALANCE (SINGLETON) ----------------
    bank_balance_obj, _ = BankBalance.objects.get_or_create(id=1)
    bank_balance = bank_balance_obj.amount

    # ---------------- COMPANY DUES ----------------
    company_dues = DailyPayment.objects.filter(
        date__year=selected_year,
        date__month=selected_month
    ).values(
        company_name=F('company__name'),
        company_id=F('company')
    ).annotate(
        total_invoice=Coalesce(Sum('invoice_amount'), 0, output_field=DecimalField(max_digits=12, decimal_places=2)),
        total_paid=Coalesce(Sum('paid_amount'), 0, output_field=DecimalField(max_digits=12, decimal_places=2)),
        total_due=ExpressionWrapper(
            F('total_invoice') - F('total_paid'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    ).order_by('company_name')

    # attach global last updated date per company (not month filtered)
    company_dues_list = []
    for c in company_dues:
        last_date = DailyPayment.objects.filter(company_id=c['company_id']).aggregate(
            last=Max('date')
        )['last']
        c['last_updated'] = last_date
        if c['total_due'] != 0:
            company_dues_list.append(c)

    company_dues = company_dues_list
    total_company_dues = sum(c["total_due"] for c in company_dues)

    # ---------------- CUSTOMER DUES (SOURCE OF TRUTH = due field) ----------------
    total_customer_dues = Customer.objects.filter(due__gt=0).aggregate(
        total=Coalesce(Sum('due'), 0, output_field=DecimalField(max_digits=12, decimal_places=2))
    )['total']

    # ---------------- MONTHLY PROFIT ----------------
    monthly_profit = Bill.objects.filter(
        invoice_date__year=selected_year,
        invoice_date__month=selected_month,
        is_deleted=False
    ).aggregate(total_profit=Sum('profit'))['total_profit'] or 0

    net_profit = monthly_profit - total_cash_out
    net_cash = total_cash_in + bank_balance

    # ---------------- STOCK VALUE ----------------
    total_stock_value = Item.objects.aggregate(
        total=Sum(F('stock_quantity') * F('buying_price'))
    )['total'] or 0

    # ---------------- REMAINING AMOUNT ----------------
    remaining_amount = (
        net_cash
        + total_stock_value
        - net_profit
        - total_company_dues
        + total_customer_dues
    )

    context = {
        'cash_entry': cash_entry,
        'cash_out_entries': cash_out_entries,
        'total_cash_in': total_cash_in,
        'total_cash_out': total_cash_out,
        'net_cash': net_cash,
        'bank_balance': bank_balance,
        'current_date': today.strftime('%Y-%m-%d'),
        'company_dues': company_dues,
        'total_company_dues': total_company_dues,
        'total_customer_dues': total_customer_dues,
        'monthly_profit': monthly_profit,
        'net_profit': net_profit,
        'denomination_totals': denomination_totals,
        'total_stock_value': total_stock_value,
        'remaining_amount': remaining_amount,
        'months': months,
        'years': years,
        'selected_month': selected_month,
        'selected_year': selected_year,
    }

    return render(request, 'milk_agency/dashboards_other/cashbook.html', context)


# -------------------------------------------------------
# SAVE BANK BALANCE
# -------------------------------------------------------
@login_required
def save_bank_balance(request):
    if request.method == 'POST':
        amount_str = request.POST.get('amount', '').strip()

        if amount_str == '':
            messages.error(request, "Amount cannot be empty")
            return redirect('milk_agency:cashbook')

        try:
            amount = float(amount_str)
            bank_balance_obj, _ = BankBalance.objects.get_or_create(id=1)
            bank_balance_obj.amount = amount
            bank_balance_obj.save()
            messages.success(request, f"Bank balance updated: ₹{amount:.2f}")
        except ValueError:
            messages.error(request, "Invalid amount format")

    return redirect('milk_agency:cashbook')
# -------------------------------------------------------
# SAVE CASH-IN
# -------------------------------------------------------
@login_required
def save_cash_in(request):
    if request.method == 'POST':
        denominations = [
            'c500', 'c200', 'c100', 'c50',
            'c20', 'c10', 'coin20', 'coin10',
            'coin5', 'coin2', 'coin1'
        ]

        cash_entry = CashbookEntry.objects.first() or CashbookEntry.objects.create()

        for d in denominations:
            value = request.POST.get(d, 0)
            setattr(cash_entry, d, int(value) if value else 0)

        cash_entry.save()
        messages.success(request, "Cash in updated successfully")

    return redirect('milk_agency:cashbook')


# -------------------------------------------------------
# SAVE EXPENSE
# -------------------------------------------------------
@login_required
def save_expense(request):
    if request.method == 'POST':
        try:
            Expense.objects.create(
                amount=float(request.POST.get('amount')),
                category=request.POST.get('category'),
                description=request.POST.get('description')
            )
            messages.success(request, "Expense added successfully")
        except:
            messages.error(request, "Invalid amount")

    return redirect('milk_agency:cashbook')


# -------------------------------------------------------
# EDIT EXPENSE
# -------------------------------------------------------
@login_required
def edit_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk)

    if request.method == 'POST':
        try:
            expense.amount = float(request.POST.get('amount'))
            expense.category = request.POST.get('category')
            expense.description = request.POST.get('description')
            expense.date = request.POST.get('date')
            expense.save()
            messages.success(request, "Expense updated successfully")
            return redirect('milk_agency:expenses_list')
        except:
            messages.error(request, "Invalid amount")

    return render(request, 'milk_agency/dashboards_other/edit_expense.html', {'expense': expense})


# -------------------------------------------------------
# DELETE EXPENSE
# -------------------------------------------------------
@login_required
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk)

    if request.method == 'POST':
        amount = expense.amount
        category = expense.category
        expense.delete()
        messages.success(request, f"Expense deleted: ₹{amount} ({category})")
        return redirect('milk_agency:expenses_list')

    return render(request, 'milk_agency/dashboards_other/delete_expense.html', {'expense': expense})


# -------------------------------------------------------
# EXPENSE LIST
# -------------------------------------------------------
@login_required
def expenses_list(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    today = timezone.now().date()

    if not start_date:
        start_date = today.replace(day=1).strftime('%Y-%m-%d')

    if not end_date:
        next_month = today.replace(day=28) + timezone.timedelta(days=4)
        last_day = next_month - timezone.timedelta(days=next_month.day)
        end_date = last_day.strftime('%Y-%m-%d')

    expenses = Expense.objects.filter(
        date__range=[start_date, end_date]
    ).order_by('-date')

    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0

    chart_data = expenses.values('category').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('category')

    chart_labels = [item['category'].title() for item in chart_data]
    chart_values = [float(item['total']) for item in chart_data]

    context = {
        'expenses': expenses,
        'total_expenses': total_expenses,
        'start_date': start_date,
        'end_date': end_date,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
    }

    return render(request, 'milk_agency/dashboards_other/expenses_list.html', context)