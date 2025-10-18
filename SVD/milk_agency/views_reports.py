import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse, Http404
from .models import Bill, Customer
from .utils import InvoicePDFUtils

from django.core.paginator import Paginator
from datetime import date

def reports_dashboard(request):
    # Get all invoices with related data
    invoices = Bill.objects.select_related('customer').all().order_by('-invoice_date')
    # Get all customers with related data
    customers = Customer.objects.all()
    total_due = customers.aggregate(total=Sum('due'))['total'] or 0

    # Get filter parameters with defaults
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    customer_id = request.GET.get('customer')
    status = request.GET.get('status')
    search_query = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', 'invoice_date')
    sort_order = request.GET.get('order', 'desc')

    # Set default date filters to current date if no filters are applied
    if not any([start_date, end_date, customer_id, status, search_query]):
        today = date.today()
        start_date = today.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    # Apply filters
    if start_date and end_date:
        invoices = invoices.filter(invoice_date__range=[start_date, end_date])

    if customer_id and customer_id != 'all':
        invoices = invoices.filter(customer_id=customer_id)

    if search_query:
        invoices = invoices.filter(
            invoice_number__icontains=search_query
        )

    # Apply sorting
    valid_sort_fields = {
        'invoice_date': 'invoice_date',
        'invoice_number': 'invoice_number',
        'customer': 'customer__name',
        'total_amount': 'total_amount'
    }

    if sort_by in valid_sort_fields:
        field = valid_sort_fields[sort_by]
        if sort_order == 'desc':
            field = f'-{field}'
        invoices = invoices.order_by(field)

    # Calculate total amount for all filtered invoices
    total_amount = invoices.aggregate(total=Sum('total_amount'))['total'] or 0

    # Pagination
    paginator = Paginator(invoices, 10)  # Show 10 invoices per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get customers for filter dropdown
    customers = Customer.objects.all().order_by('name')

    context = {
        'invoices': page_obj,
        'customers': customers,
        'start_date': start_date,
        'end_date': end_date,
        'selected_customer': customer_id,
        'selected_status': status,
        'search_query': search_query,
        'page_obj': page_obj,
        'total_amount': total_amount,
        'sort_by': sort_by,
        'sort_order': sort_order,
    }
    return render(request, 'milk_agency/dashboards_other/reports_dashboard.html', context)

def invoice_pdf_viewer(request, invoice_id):
    """View invoice PDF in a separate viewer page"""
    try:
        invoice_id = int(invoice_id)
        bill = get_object_or_404(Bill, id=invoice_id)
        pdf_path = InvoicePDFUtils.get_invoice_pdf_path(bill.invoice_number)
        if not os.path.exists(pdf_path):
            raise Http404("Invoice PDF not found")
        with open(pdf_path, 'rb') as pdf_file:
            response = HttpResponse(pdf_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename=invoice_{bill.invoice_number}.pdf'
        return response
    except Http404:
        return HttpResponse("Invoice PDF not found.", status=404)
    except ValueError:
        messages.error(request, 'Invalid invoice ID.')
        return redirect('milk_agency:reports_dashboard')
