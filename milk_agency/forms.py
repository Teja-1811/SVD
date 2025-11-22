from django import forms
from .models import Company, Item


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'logo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to widgets
        self.fields['name'].widget.attrs.update({'class': 'form-control'})
        self.fields['logo'].widget.attrs.update({'class': 'form-control'})

