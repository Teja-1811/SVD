# TODO: Add Company Model to milk_agency

## Task Description
Create a new model named Company inside milk_agency/models.py with fields for the company's name, logo image, and website link.

## Detailed Steps
- Edit milk_agency/models.py to add:
  - Company model with:
    - name (CharField, max_length=255, unique)
    - logo (ImageField, upload_to='company_logos/', blank=True, null=True)
    - website_link (URLField, blank=True)
    - __str__ method returning the company name
    - Meta class ordering by 'name'

- Edit milk_agency/admin.py to:
  - Register the Company model for Django admin interface

## Follow-up Steps
- Run `python manage.py makemigrations milk_agency`
- Run `python manage.py migrate`
- Verify model creation and admin interface functionality

## Notes
- Only necessary fields as requested are included
- Additional fields can be added later if required
