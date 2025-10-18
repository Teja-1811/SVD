from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from .models import CashbookEntry, Expense, BankBalance, MonthlyPaymentSummary, DailyPayment, Customer, Bill

def cashbook(request):
    # Get current date
    today = timezone.now().date()

    # Get the cashbook entry (assuming single instance)
    cash_entry = CashbookEntry.objects.first()
    if not cash_entry:
        cash_entry = CashbookEntry.objects.create()

    # Calculate total cash in from counts
    total_cash_in = (cash_entry.c500 * 500) + (cash_entry.c200 * 200) + (cash_entry.c100 * 100) + (cash_entry.c50 * 50)

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
    # Get company-wise dues (companies that owe money to the business)
    company_dues = []
    # Get the latest monthly summary for each company with outstanding dues
    companies_with_dues = MonthlyPaymentSummary.objects.filter(
        total_due__gt=0
    ).values('year', 'month', 'total_invoice', 'total_paid', 'total_due').order_by('-year', '-month')

    # Group by company (we need to get company names from DailyPayment records)
    company_totals = {}
    for summary in companies_with_dues:
        # Find the company name from DailyPayment records for this month
        daily_payments = DailyPayment.objects.filter(
            date__year=summary['year'],
            date__month=summary['month']
        ).values_list('company', flat=True).distinct()

        for company in daily_payments:
            if company not in company_totals:
                company_totals[company] = {
                    'company': company,
                    'total_due': 0,
                    'last_updated': f"{summary['month']}/{summary['year']}"
                }
            company_totals[company]['total_due'] += summary['total_due']

    company_dues = list(company_totals.values())
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
    net_cash = total_cash_in + bank_balance + total_customer_dues - total_company_dues

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
        'net_profit': net_profit
    }
    return render(request, 'milk_agency/dashboards_other/cashbook.html', context)

def save_cash_in(request):
    if request.method == 'POST':
        c500 = request.POST.get('c500', 0)
        c200 = request.POST.get('c200', 0)
        c100 = request.POST.get('c100', 0)
        c50 = request.POST.get('c50', 0)

        try:
            c500 = int(c500) if c500 else 0
            c200 = int(c200) if c200 else 0
            c100 = int(c100) if c100 else 0
            c50 = int(c50) if c50 else 0

            # Get or create cash entry
            cash_entry = CashbookEntry.objects.first()
            if not cash_entry:
                cash_entry = CashbookEntry.objects.create()
            cash_entry.c500 = c500
            cash_entry.c200 = c200
            cash_entry.c100 = c100
            cash_entry.c50 = c50
            cash_entry.save()

            amount = (c500 * 500) + (c200 * 200) + (c100 * 100) + (c50 * 50)
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
