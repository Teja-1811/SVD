from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, F
from django.urls import reverse
from django import forms
from .models import Item, Company


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'logo', 'website_link']


def add_company(request):
    if request.method == 'POST':
        form = CompanyForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect(reverse('milk_agency:companies_dashboard'))
    else:
        form = CompanyForm()
    return render(request, 'milk_agency/company_form.html', {'form': form, 'form_title': 'Add Company'})


def edit_company(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    if request.method == 'POST':
        form = CompanyForm(request.POST, request.FILES, instance=company)
        if form.is_valid():
            form.save()
            return redirect(reverse('milk_agency:companies_dashboard'))
    else:
        form = CompanyForm(instance=company)
    return render(request, 'milk_agency/company_form.html', {'form': form, 'form_title': 'Edit Company'})


def companies_dashboard(request):
    """Display company cards with logo + details + items count + stock info."""
    
    companies = Company.objects.all().order_by('name')

    # Add computed fields to each company
    for c in companies:
        item_stats = Item.objects.filter(company=c).aggregate(
            total_items=Sum(1),   # counts items
            total_qty=Sum('stock_quantity'),
            total_value=Sum(F('stock_quantity') * F('buying_price'))
        )

        c.total_items = item_stats['total_items'] or 0
        c.total_qty = item_stats['total_qty'] or 0
        c.total_value = item_stats['total_value'] or 0

    return render(request, 'milk_agency/dashboards_other/companies_dashboard.html', {
        'companies': companies
    })
