from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django import forms
from .models import Company

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
