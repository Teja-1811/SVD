from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Sum, F
from django.utils import timezone
from .models import CashbookEntry, Investment, BankBalance, Customer, Sale, Expense, Product

def cashbook(request):
    # Get current date
    today = timezone.now().date()

    # Get the cashbook entry (assuming single instance)
    cash_entry = CashbookEntry.objects.first()
    if not cash_entry:
        cash_entry = CashbookEntry.objects.create()

    # Calculate total cash in from counts
    total_cash_in = (cash_entry.c500 * 500) + (cash_entry.c200 * 200) + (cash_entry.c100 * 100) + (cash_entry.c50 * 50) + (cash_entry.c20 * 20) + (cash_entry.c10 * 10)

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

    # Calculate total dues from customers (balance field in general_store)
    total_customer_dues = Customer.objects.aggregate(total_balance=Sum('balance'))['total_balance'] or 0

    # Calculate current month profit from sales
    current_month = today.month
    current_year = today.year
    monthly_profit = Sale.objects.filter(
        invoice_date__year=current_year,
        invoice_date__month=current_month
    ).aggregate(total_profit=Sum('profit'))['total_profit'] or 0

    # Calculate net profit = monthly profit - current month expenses
    net_profit = monthly_profit - total_cash_out

    # Calculate net cash (cash in hand + bank balance + customer dues)
    net_cash = total_cash_in + bank_balance + total_customer_dues

    # Calculate total stock value
    total_stock_value = Product.objects.aggregate(
        total=Sum(F('stock_quantity') * F('buying_price'))
    )['total'] or 0

    context = {
        'cash_entry': cash_entry,
        'cash_out_entries': cash_out_entries,
        'total_cash_in': total_cash_in,
        'total_cash_out': total_cash_out,
        'net_cash': net_cash,
        'bank_balance': bank_balance,
        'current_date': today.strftime('%Y-%m-%d'),
        'total_customer_dues': total_customer_dues,
        'monthly_profit': monthly_profit,
        'net_profit': net_profit,
        'total_stock_value': total_stock_value
    }
    return render(request, 'general_store/cashbook.html', context)

def save_cash_in(request):
    if request.method == 'POST':
        c500 = request.POST.get('c500', 0)
        c200 = request.POST.get('c200', 0)
        c100 = request.POST.get('c100', 0)
        c50 = request.POST.get('c50', 0)
        c20 = request.POST.get('c20', 0)
        c10 = request.POST.get('c10', 0)

        try:
            c500 = int(c500) if c500 else 0
            c200 = int(c200) if c200 else 0
            c100 = int(c100) if c100 else 0
            c50 = int(c50) if c50 else 0
            c20 = int(c20) if c20 else 0
            c10 = int(c10) if c10 else 0

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
            cash_entry.save()

            amount = (c500 * 500) + (c200 * 200) + (c100 * 100) + (c50 * 50) + (c20 * 20) + (c10 * 10)
            messages.success(request, f'Cash in updated: ₹{amount}')
        except ValueError:
            messages.error(request, 'Invalid values for counts')

    return redirect('general_store:cashbook')

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

    return redirect('general_store:cashbook')

def investments_list(request):
    # Get filter parameters from request
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Get current date for default values
    today = timezone.now().date()

    # Set default filter values if not provided (current month)
    if not start_date:
        start_date = today.replace(day=1).strftime('%Y-%m-%d')  # First day of current month
    if not end_date:
        # Last day of current month
        next_month = today.replace(day=28) + timezone.timedelta(days=4)  # This will never fail
        last_day = next_month - timezone.timedelta(days=next_month.day)
        end_date = last_day.strftime('%Y-%m-%d')

    # Filter investments based on date range
    investments = Investment.objects.filter(
        date__range=[start_date, end_date]
    ).order_by('-date')

    # Calculate total investments for the filtered period
    total_investments = investments.aggregate(total=Sum('amount'))['total'] or 0

    # Prepare chart data: investments grouped by category
    from django.db.models import Count
    chart_data = investments.values('category').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('category')

    chart_labels = [item['category'] for item in chart_data]
    chart_values = [float(item['total']) for item in chart_data]

    context = {
        'investments': investments,
        'total_investments': total_investments,
        'start_date': start_date,
        'end_date': end_date,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
    }
    return render(request, 'general_store/investments_list.html', context)

def expenses_list(request):
    # Get filter parameters from request
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Get current date for default values
    today = timezone.now().date()

    # Set default filter values if not provided (current month)
    if not start_date:
        start_date = today.replace(day=1).strftime('%Y-%m-%d')  # First day of current month
    if not end_date:
        # Last day of current month
        next_month = today.replace(day=28) + timezone.timedelta(days=4)  # This will never fail
        last_day = next_month - timezone.timedelta(days=next_month.day)
        end_date = last_day.strftime('%Y-%m-%d')

    # Filter expenses based on date range
    expenses = Expense.objects.filter(
        date__range=[start_date, end_date]
    ).order_by('-date')

    # Calculate total expenses for the filtered period
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0

    # Prepare chart data: expenses grouped by category
    from django.db.models import Count
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
    return render(request, 'general_store/expenses_list.html', context)

def save_investment(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        category = request.POST.get('category')
        description = request.POST.get('description')

        try:
            amount = float(amount)

            # Create investment
            Investment.objects.create(
                amount=amount,
                category=category,
                description=description
            )

            messages.success(request, f'Investment added: ₹{amount} ({category})')
        except ValueError:
            messages.error(request, 'Invalid amount value')

    return redirect('general_store:investments_list')

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

    return redirect('general_store:cashbook')
