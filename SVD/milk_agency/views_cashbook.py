from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Sum, Max, F, ExpressionWrapper, DecimalField, FloatField
from django.db.models.functions import Coalesce
from django.utils import timezone
from .models import CashbookEntry, Expense, BankBalance, MonthlyPaymentSummary, DailyPayment, Customer, Bill, Item

def cashbook(request):
    # Get current date
    today = timezone.now().date()

    # Get the cashbook entry (assuming single instance)
    cash_entry = CashbookEntry.objects.first()
    if not cash_entry:
        cash_entry = CashbookEntry.objects.create()

    # Calculate total cash in from counts
    total_cash_in = (cash_entry.c500 * 500) + (cash_entry.c200 * 200) + (cash_entry.c100 * 100) + (cash_entry.c50 * 50) + (cash_entry.c20 * 20) + (cash_entry.c10 * 10) + (cash_entry.coin20 * 20) + (cash_entry.coin10 * 10) + (cash_entry.coin5 * 5) + (cash_entry.coin2 * 2) + (cash_entry.coin1 * 1)

    # Calculate denomination-wise totals
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

    # Get current month expenses as cash out
    current_month = today.month
    current_year = today.year
    cash_out_entries = Expense.objects.filter(date__year=current_year, date__month=current_month).order_by('-created_at')

    # Calculate total cash out
    total_cash_out = cash_out_entries.aggregate(total=Sum('amount'))['total'] or 0
    

    # Get bank balance
    bank_balance = BankBalance.objects.first()
    if bank_balance:
        bank_balance = bank_balance.amount
    else:
        bank_balance = 0
    # Get all company-wise dues for current month (including companies the business owes money to and companies that owe the business money)
    company_dues = DailyPayment.objects.filter(
        date__year=current_year,
        date__month=current_month
    ).values('company').annotate(
        total_invoice=Coalesce(Sum('invoice_amount'), 0, output_field=DecimalField(max_digits=12, decimal_places=2)),
        total_paid=Coalesce(Sum('paid_amount'), 0, output_field=DecimalField(max_digits=12, decimal_places=2)),
        total_due=ExpressionWrapper(
            F('total_invoice') - F('total_paid'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),
        last_updated=Max('date')
    ).order_by('company')

    # Filter out companies with no dues (total_due is None or 0)
    company_dues = [company for company in company_dues if company['total_due'] != 0]

    total_company_dues = sum(company['total_due'] for company in company_dues)

    # Calculate total dues from customers
    total_customer_dues = Customer.objects.aggregate(total_due=Sum('due'))['total_due'] or 0

    # Calculate current month profit from bills
    current_month = today.month
    current_year = today.year
    monthly_profit = Bill.objects.filter(
        invoice_date__year=current_year,
        invoice_date__month=current_month
    ).aggregate(total_profit=Sum('profit'))['total_profit'] or 0

    # Calculate net profit = monthly profit - current month expenses
    net_profit = monthly_profit - total_cash_out

    # Calculate net cash
    net_cash = total_cash_in + bank_balance + total_customer_dues

    # Calculate total stock value
    total_stock_value = Item.objects.aggregate(
        total=Sum(F('stock_quantity') * F('buying_price'))
    )['total'] or 0

    # Calculate remaining amount
    remaining_amount = net_cash + total_stock_value - net_profit - total_company_dues

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
        'remaining_amount': remaining_amount
    }
    return render(request, 'milk_agency/dashboards_other/cashbook.html', context)

def save_cash_in(request):
    if request.method == 'POST':
        c500 = request.POST.get('c500', 0)
        c200 = request.POST.get('c200', 0)
        c100 = request.POST.get('c100', 0)
        c50 = request.POST.get('c50', 0)
        c20 = request.POST.get('c20', 0)
        c10 = request.POST.get('c10', 0)
        coin20 = request.POST.get('coin20', 0)
        coin10 = request.POST.get('coin10', 0)
        coin5 = request.POST.get('coin5', 0)
        coin2 = request.POST.get('coin2', 0)
        coin1 = request.POST.get('coin1', 0)

        try:
            c500 = int(c500) if c500 else 0
            c200 = int(c200) if c200 else 0
            c100 = int(c100) if c100 else 0
            c50 = int(c50) if c50 else 0
            c20 = int(c20) if c20 else 0
            c10 = int(c10) if c10 else 0
            coin20 = int(coin20) if coin20 else 0
            coin10 = int(coin10) if coin10 else 0
            coin5 = int(coin5) if coin5 else 0
            coin2 = int(coin2) if coin2 else 0
            coin1 = int(coin1) if coin1 else 0

            # Get or create cash entry
            cash_entry = CashbookEntry.objects.first()
            if not cash_entry:
                cash_entry = CashbookEntry.objects.create()
            cash_entry.c500 = c500
            cash_entry.c200 = c200
            cash_entry.c100 = c100
            cash_entry.c50 = c50
            cash_entry.c20 = c20
            cash_entry.c10 = c10
            cash_entry.coin20 = coin20
            cash_entry.coin10 = coin10
            cash_entry.coin5 = coin5
            cash_entry.coin2 = coin2
            cash_entry.coin1 = coin1
            cash_entry.save()

            amount = (c500 * 500) + (c200 * 200) + (c100 * 100) + (c50 * 50) + (c20 * 20) + (c10 * 10) + (coin20 * 20) + (coin10 * 10) + (coin5 * 5) + (coin2 * 2) + (coin1 * 1)
            messages.success(request, f'Cash in updated: ₹{amount}')
        except ValueError:
            messages.error(request, 'Invalid values for counts')

    return redirect('milk_agency:cashbook')

def save_expense(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        category = request.POST.get('category')
        description = request.POST.get('description')

        try:
            amount = float(amount)

            # Create expense
            Expense.objects.create(
                amount=amount,
                category=category,
                description=description
            )

            messages.success(request, f'Expense added: ₹{amount} ({category})')
        except ValueError:
            messages.error(request, 'Invalid amount value')

    return redirect('milk_agency:cashbook')

def expenses_list(request):
    expenses = Expense.objects.all().order_by('-date')

    # Calculate total expenses
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'expenses': expenses,
        'total_expenses': total_expenses
    }
    return render(request, 'milk_agency/dashboards_other/expenses_list.html', context)

def save_bank_balance(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')

        try:
            amount = float(amount)

            # Update or create bank balance
            bank_balance, created = BankBalance.objects.get_or_create(
                defaults={'amount': amount}
            )
            if not created:
                bank_balance.amount = amount
                bank_balance.save()

            messages.success(request, f'Bank balance updated: ₹{amount}')
        except ValueError:
            messages.error(request, 'Invalid amount value')

    return redirect('milk_agency:cashbook')
