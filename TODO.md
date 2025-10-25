# TODO: Remove Date Filter from Bills Dashboard

- [x] Edit SVD/templates/milk_agency/bills/bills_dashboard.html: Remove date input fields (From Date and To Date) from the filters section
- [x] Edit SVD/templates/milk_agency/bills/bills_dashboard.html: Adjust the clear filters button logic to only consider customer filter
- [x] Edit SVD/milk_agency/views_bills.py: Remove date filtering logic from bills_dashboard view
- [x] Edit SVD/milk_agency/views_bills.py: Remove date_from and date_to from context
