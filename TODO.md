# TODO: Remove last_paid_balance from Customer Model

- [x] Edit SVD/milk_agency/models.py to remove the 'last_paid_balance' field from the Customer class.
- [x] Run `python manage.py makemigrations milk_agency` to generate a migration for the field removal.
- [x] Run `python manage.py migrate` to apply the migration and update the database schema.
- [x] Update SVD/milk_agency/views_customer.py to remove references to last_paid_balance.
- [x] Update SVD/milk_agency/views_bills.py to remove references to last_paid_balance.
- [x] Test the application to ensure no errors after the field removal.
