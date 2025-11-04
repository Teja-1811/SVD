# Item Freeze Function Development

## Tasks
- [x] Add `frozen` field to Item model
- [x] Create migration for the new field
- [x] Add freeze/unfreeze item view in views_items.py
- [x] Add URL for freeze/unfreeze item
- [x] Update all Item queries to exclude frozen items except in items_dashboard
- [x] Update items_dashboard template to show freeze status and button
- [x] Test the functionality

## Files to Modify
- SVD/milk_agency/models.py: Add frozen field to Item model
- SVD/milk_agency/views_items.py: Add freeze_item view and update items_dashboard to show frozen status
- SVD/milk_agency/urls.py: Add URL for freeze_item
- SVD/milk_agency/views.py: Update Item.objects.all() queries to exclude frozen
- SVD/milk_agency/views_dodla.py: Update Item.objects.all() to exclude frozen
- SVD/milk_agency/views_stock_dashboard.py: Update Item.objects.all() to exclude frozen
- SVD/milk_agency/views_bill_operations.py: Update Item.objects.all() to exclude frozen
- SVD/milk_agency/views_bills.py: Update Item.objects.all() to exclude frozen
- SVD/customer_portal/views.py: Update Item.objects.all() to exclude frozen
- SVD/SVD/urls.py: Update index view to exclude frozen items
- Templates: Update items_dashboard.html to show freeze/unfreeze buttons and status
