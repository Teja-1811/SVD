from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max, F, ExpressionWrapper, DecimalField, Count
from django.db.models.functions import Coalesce
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from datetime import datetime

from .models import (
    CashbookEntry, Expense, BankBalance,
    MonthlyPaymentSummary, DailyPayment,
    Customer, Bill, Item, Company, LeakageEntry, CustomerPayment
)

DELIVERY_DUE_EXPENSE_CATEGORIES = {"Fuel", "Food", "Repair"}


def _safe_redirect_target(raw_target, fallback):
    if raw_target and raw_target.startswith("/"):
        return redirect(raw_target)
    return redirect(fallback)


def _get_delivery_customer():
    return Customer.objects.filter(shop_name__iexact="Delivery").order_by("id").first()


def _get_latest_bill(customer):
    if not customer:
        return None
    return (
        Bill.objects.filter(customer=customer, is_deleted=False)
        .order_by("-invoice_date", "-id")
        .first()
    )


def _expense_affects_delivery_due(category):
    if category not in DELIVERY_DUE_EXPENSE_CATEGORIES:
        return False
    return True


def _adjust_delivery_due(customer, amount, category, subtract=True):
    if not customer or not _expense_affects_delivery_due(category):
        return

    delta = Decimal(amount)
    if subtract:
        delta = -delta

    Customer.objects.filter(pk=customer.pk).update(due=F("due") + delta)


def _recalculate_bill_last_paid(bill):
    if not bill:
        return

    total_paid = (
        CustomerPayment.objects.filter(bill=bill, status="SUCCESS")
        .aggregate(total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2)))["total"]
    )
    bill.last_paid = total_paid
    bill.save(update_fields=["last_paid"])


def _sync_delivery_expense_payment(customer, expense):
    if not customer:
        return

    payment_qs = CustomerPayment.objects.filter(transaction_id=f"EXPENSE-{expense.pk}")
    old_bill = payment_qs.first().bill if payment_qs.exists() else None

    if not _expense_affects_delivery_due(expense.category):
        payment_qs.delete()
        _recalculate_bill_last_paid(old_bill)
        return

    latest_bill = _get_latest_bill(customer)
    payment_qs.update_or_create(
        transaction_id=f"EXPENSE-{expense.pk}",
        defaults={
            "customer": customer,
            "bill": latest_bill,
            "amount": Decimal(expense.amount),
            "method": "Expense",
            "status": "SUCCESS",
        },
    )
    if old_bill and latest_bill and old_bill.pk != latest_bill.pk:
        _recalculate_bill_last_paid(old_bill)
    _recalculate_bill_last_paid(latest_bill)


def _delete_delivery_expense_payment(expense):
    payment = CustomerPayment.objects.filter(transaction_id=f"EXPENSE-{expense.pk}").first()
    if not payment:
        return

    bill = payment.bill
    payment.delete()
    _recalculate_bill_last_paid(bill)


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
    bank_balance_obj, _ = BankBalance.objects.get_or_create(
        id=1,
        defaults={'amount': 0}
    )
    bank_balance = bank_balance_obj.amount

    # ---------------- COMPANY DUES ----------------
    company_dues_qs = DailyPayment.objects.filter(
        date__year=selected_year,
        date__month=selected_month
    ).values(
        'company',
        'company__name'
    ).annotate(
        total_invoice=Coalesce(Sum('invoice_amount'), 0, output_field=DecimalField(max_digits=12, decimal_places=2)),
        total_paid=Coalesce(Sum('paid_amount'), 0, output_field=DecimalField(max_digits=12, decimal_places=2)),
        total_due=ExpressionWrapper(
            F('total_invoice') - F('total_paid'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    ).order_by('company__name')

    # Attach latest overall date per company
    company_dues = []
    for c in company_dues_qs:
        last_date = DailyPayment.objects.filter(company=c['company']).aggregate(
            last=Max('date')
        )['last']

        if c['total_due'] != 0:
            company_dues.append({
                "company_name": c['company__name'],
                "total_due": c['total_due'],
                "last_updated": last_date
            })

    total_company_dues = sum(c["total_due"] for c in company_dues)

    # ---------------- CUSTOMER DUES (SOURCE OF TRUTH = due field) ----------------
    total_customer_dues = Customer.objects.filter(due__gt=0).aggregate(
        total=Coalesce(Sum('due'), 0, output_field=DecimalField(max_digits=12, decimal_places=2))
    )['total']

    # ---------------- LEAKAGE / LOSS ----------------
    leakage_entries = LeakageEntry.objects.filter(
        date__year=selected_year,
        date__month=selected_month
    ).select_related('item', 'item__company')

    monthly_loss = leakage_entries.aggregate(
        total=Coalesce(Sum('total_loss'), 0, output_field=DecimalField(max_digits=12, decimal_places=2))
    )['total']

    # ---------------- MONTHLY PROFIT ----------------
    monthly_profit = Bill.objects.filter(
        invoice_date__year=selected_year,
        invoice_date__month=selected_month,
        is_deleted=False
    ).aggregate(total_profit=Sum('profit'))['total_profit'] or 0

    net_profit = monthly_profit - total_cash_out - monthly_loss
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
        'monthly_loss': monthly_loss,
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
            bank_balance_obj, _ = BankBalance.objects.get_or_create(
                id=1,
                defaults={'amount': 0}
            )
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
            amount = Decimal(request.POST.get('amount'))
            category = (request.POST.get('category') or '').strip()
            expense_date = (request.POST.get('date') or '').strip()
            delivery_customer = _get_delivery_customer()

            try:
                expense_date_obj = datetime.strptime(expense_date, '%Y-%m-%d').date() if expense_date else timezone.localdate()
            except ValueError:
                messages.error(request, "Invalid expense date")
                return _safe_redirect_target(request.POST.get('next'), 'milk_agency:cashbook')

            with transaction.atomic():
                expense = Expense.objects.create(
                    amount=amount,
                    category=category,
                    description=request.POST.get('description'),
                    date=expense_date_obj
                )
                _adjust_delivery_due(delivery_customer, amount, category, subtract=True)
                _sync_delivery_expense_payment(delivery_customer, expense)
            messages.success(request, "Expense added successfully")
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, "Invalid amount")

    return _safe_redirect_target(request.POST.get('next'), 'milk_agency:cashbook')


# -------------------------------------------------------
# SAVE LEAKAGE
# -------------------------------------------------------
@login_required
def save_leakage(request):
    if request.method == 'POST':
        next_url = request.POST.get('next')
        item_id = request.POST.get('item')
        quantity_str = (request.POST.get('quantity') or '').strip()
        leakage_date = (request.POST.get('date') or '').strip()
        notes = (request.POST.get('notes') or '').strip()

        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, "Leakage quantity must be greater than 0.")
            return _safe_redirect_target(next_url, 'milk_agency:cashbook')

        try:
            leakage_date_obj = datetime.strptime(leakage_date, '%Y-%m-%d').date() if leakage_date else timezone.localdate()
        except ValueError:
            messages.error(request, "Invalid leakage date.")
            return _safe_redirect_target(next_url, 'milk_agency:cashbook')

        with transaction.atomic():
            item = get_object_or_404(Item.objects.select_for_update(), id=item_id, frozen=False)

            if item.stock_quantity < quantity:
                messages.error(
                    request,
                    f"Leakage quantity for {item.name} cannot exceed available stock ({item.stock_quantity})."
                )
                return _safe_redirect_target(next_url, 'milk_agency:cashbook')

            item.stock_quantity -= quantity
            item.save(update_fields=['stock_quantity'])

            LeakageEntry.objects.create(
                item=item,
                date=leakage_date_obj,
                quantity=quantity,
                unit_cost=item.buying_price,
                notes=notes,
            )

        messages.success(request, f"Leakage recorded for {item.name}. Stock reduced by {quantity}.")

    return _safe_redirect_target(request.POST.get('next'), 'milk_agency:cashbook')


# -------------------------------------------------------
# DELETE LEAKAGE
# -------------------------------------------------------
@login_required
def delete_leakage(request, pk):
    leakage = get_object_or_404(LeakageEntry.objects.select_related('item'), pk=pk)

    if request.method == 'POST':
        next_url = request.POST.get('next')
        with transaction.atomic():
            item = Item.objects.select_for_update().get(pk=leakage.item_id)
            item.stock_quantity += leakage.quantity
            item.save(update_fields=['stock_quantity'])
            item_name = item.name
            restored_qty = leakage.quantity
            leakage.delete()

        messages.success(request, f"Leakage entry removed for {item_name}. Restored {restored_qty} stock.")

        return _safe_redirect_target(next_url, 'milk_agency:cashbook')

    return _safe_redirect_target(request.GET.get('next'), 'milk_agency:cashbook')


# -------------------------------------------------------
# EDIT EXPENSE
# -------------------------------------------------------
@login_required
def edit_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk)

    if request.method == 'POST':
        try:
            old_amount = Decimal(expense.amount)
            old_category = expense.category

            new_amount = Decimal(request.POST.get('amount'))
            new_category = (request.POST.get('category') or '').strip()
            delivery_customer = _get_delivery_customer()

            with transaction.atomic():
                _adjust_delivery_due(delivery_customer, old_amount, old_category, subtract=False)

                expense.amount = new_amount
                expense.category = new_category
                expense.description = request.POST.get('description')
                expense.date = request.POST.get('date')
                expense.save()

                _adjust_delivery_due(delivery_customer, new_amount, new_category, subtract=True)
                _sync_delivery_expense_payment(delivery_customer, expense)
            messages.success(request, "Expense updated successfully")
            return redirect('milk_agency:expenses_list')
        except (InvalidOperation, TypeError, ValueError):
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
        delivery_customer = _get_delivery_customer()

        with transaction.atomic():
            _adjust_delivery_due(delivery_customer, amount, category, subtract=False)
            _delete_delivery_expense_payment(expense)
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
        'expense_categories': Expense.CATEGORY_CHOICES,
        'today': today.strftime('%Y-%m-%d'),
    }

    return render(request, 'milk_agency/dashboards_other/expenses_list.html', context)
