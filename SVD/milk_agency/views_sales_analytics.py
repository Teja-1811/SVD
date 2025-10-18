from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Bill

def sales_dashboard(request):
    """Main sales dashboard view"""
    return render(request, 'milk_agency/dashboards_other/sales_dashboard.html')

def get_weekly_sales(request):
    """Get weekly sales data for line chart"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=7)

    # Get daily sales for last 7 days
    daily_sales = Bill.objects.filter(
        invoice_date__range=[start_date, end_date]
    ).extra(select={'date': "date(invoice_date)"}).values('date').annotate(
        total_sales=Sum('total_amount'),
        total_paid=Sum('last_paid'),
        total_due=Sum('op_due_amount'),
        bill_count=Count('id')
    ).order_by('date')

    # Format data for Chart.js
    labels = []
    sales_data = []
    paid_data = []
    due_data = []

    for sale in daily_sales:
        labels.append(datetime.strptime(sale['date'], '%Y-%m-%d').strftime('%d %b'))
        sales_data.append(float(sale['total_sales'] or 0))
        paid_data.append(float(sale['total_paid'] or 0))
        due_data.append(float(sale['total_due'] or 0))

    return JsonResponse({
        'labels': labels,
        'datasets': [
            {
                'label': 'Total Sales',
                'data': sales_data,
                'borderColor': 'rgb(75, 192, 192)',
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'tension': 0.4
            },
            {
                'label': 'Paid Amount',
                'data': paid_data,
                'borderColor': 'rgb(54, 162, 235)',
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'tension': 0.4
            },
            {
                'label': 'Due Amount',
                'data': due_data,
                'borderColor': 'rgb(255, 99, 132)',
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'tension': 0.4
            }
        ]
    })

def get_monthly_sales(request):
    """Get monthly sales data for line chart"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)

    daily_sales = Bill.objects.filter(
        invoice_date__range=[start_date, end_date]
    ).extra(select={'date': "date(invoice_date)"}).values('date').annotate(
        total_sales=Sum('total_amount'),
        total_paid=Sum('last_paid'),
        total_due=Sum('op_due_amount'),
        bill_count=Count('id')
    ).order_by('date')

    labels = []
    sales_data = []
    paid_data = []
    due_data = []

    for sale in daily_sales:
        labels.append(datetime.strptime(sale['date'], '%Y-%m-%d').strftime('%d %b'))
        sales_data.append(float(sale['total_sales'] or 0))
        paid_data.append(float(sale['total_paid'] or 0))
        due_data.append(float(sale['total_due'] or 0))

    return JsonResponse({
        'labels': labels,
        'datasets': [
            {
                'label': 'Total Sales',
                'data': sales_data,
                'borderColor': 'rgb(75, 192, 192)',
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'tension': 0.4
            },
            {
                'label': 'Paid Amount',
                'data': paid_data,
                'borderColor': 'rgb(54, 162, 235)',
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'tension': 0.4
            },
            {
                'label': 'Due Amount',
                'data': due_data,
                'borderColor': 'rgb(255, 99, 132)',
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'tension': 0.4
            }
        ]
    })

def get_yearly_sales(request):
    """Get yearly sales data for line chart"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=365)

    monthly_sales = Bill.objects.filter(
        invoice_date__range=[start_date, end_date]
    ).annotate(
        month=TruncMonth('invoice_date')
    ).values('month').annotate(
        total_sales=Sum('total_amount'),
        total_paid=Sum('last_paid'),
        total_due=Sum('op_due_amount'),
        bill_count=Count('id')
    ).order_by('month')

    labels = []
    sales_data = []
    paid_data = []
    due_data = []

    for sale in monthly_sales:
        labels.append(sale['month'].strftime('%b %Y'))
        sales_data.append(float(sale['total_sales'] or 0))
        paid_data.append(float(sale['total_paid'] or 0))
        due_data.append(float(sale['total_due'] or 0))

    return JsonResponse({
        'labels': labels,
        'datasets': [
            {
                'label': 'Total Sales',
                'data': sales_data,
                'borderColor': 'rgb(75, 192, 192)',
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'tension': 0.4
            },
            {
                'label': 'Paid Amount',
                'data': paid_data,
                'borderColor': 'rgb(54, 162, 235)',
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'tension': 0.4
            },
            {
                'label': 'Due Amount',
                'data': due_data,
                'borderColor': 'rgb(255, 99, 132)',
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'tension': 0.4
            }
        ]
    })

def get_overall_sales(request):
    """Get overall cumulative sales data"""
    all_bills = Bill.objects.all().order_by('invoice_date')

    cumulative_sales = []
    cumulative_paid = []
    cumulative_due = []
    labels = []

    running_total_sales = 0
    running_total_paid = 0
    running_total_due = 0

    for bill in all_bills:
        running_total_sales += float(bill.total_amount or 0)
        running_total_paid += float(bill.last_paid or 0)
        running_total_due += float(bill.op_due_amount or 0)

        labels.append(bill.invoice_date.strftime('%d %b %Y'))
        cumulative_sales.append(running_total_sales)
        cumulative_paid.append(running_total_paid)
        cumulative_due.append(running_total_due)

    return JsonResponse({
        'labels': labels,
        'datasets': [
            {
                'label': 'Cumulative Sales',
                'data': cumulative_sales,
                'borderColor': 'rgb(75, 192, 192)',
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'tension': 0.4
            },
            {
                'label': 'Cumulative Paid',
                'data': cumulative_paid,
                'borderColor': 'rgb(54, 162, 235)',
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'tension': 0.4
            },
            {
                'label': 'Cumulative Due',
                'data': cumulative_due,
                'borderColor': 'rgb(255, 99, 132)',
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'tension': 0.4
            }
        ]
    })

def get_filtered_sales(request):
    """Get filtered sales data based on date range"""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    daily_sales = Bill.objects.filter(
        invoice_date__range=[start_date, end_date]
    ).extra(select={'date': "date(invoice_date)"}).values('date').annotate(
        total_sales=Sum('total_amount'),
        total_paid=Sum('last_paid'),
        total_due=Sum('op_due_amount'),
        bill_count=Count('id')
    ).order_by('date')

    labels = []
    sales_data = []
    paid_data = []
    due_data = []

    for sale in daily_sales:
        labels.append(datetime.strptime(sale['date'], '%Y-%m-%d').strftime('%d %b %Y'))
        sales_data.append(float(sale['total_sales'] or 0))
        paid_data.append(float(sale['total_paid'] or 0))
        due_data.append(float(sale['total_due'] or 0))

    return JsonResponse({
        'labels': labels,
        'datasets': [
            {
                'label': 'Total Sales',
                'data': sales_data,
                'borderColor': 'rgb(75, 192, 192)',
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'tension': 0.4
            },
            {
                'label': 'Paid Amount',
                'data': paid_data,
                'borderColor': 'rgb(54, 162, 235)',
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'tension': 0.4
            },
            {
                'label': 'Due Amount',
                'data': due_data,
                'borderColor': 'rgb(255, 99, 132)',
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'tension': 0.4
            }
        ]
    })

def get_sales_summary(request):
    """Get summary statistics for the dashboard"""
    total_sales = Bill.objects.aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    total_paid = Bill.objects.aggregate(
        total=Sum('last_paid')
    )['total'] or 0

    total_due = Bill.objects.aggregate(
        total=Sum('op_due_amount')
    )['total'] or 0

    total_bills = Bill.objects.count()

    return JsonResponse({
        'total_sales': float(total_sales),
        'total_paid': float(total_paid),
        'total_due': float(total_due),
        'total_bills': total_bills
    })
