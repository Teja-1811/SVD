# TODO: Update Sales Summary by Category Page

## Tasks
- [x] Edit `SVD/templates/milk_agency/dashboards_other/sales_summary_by_category.html`:
  - Remove the entire filter card (form) including period select, customer select, month/year fields, and "Apply Filters" button.
  - Add Bootstrap nav-tabs above the chart for time periods: Overall, Today, Current Week, Current Month, Current Year, Custom.
  - Make each tab a link that reloads the page with `?period=overall`, `?period=today`, `?period=week`, `?period=month`, `?period=year`, `?period=custom`.
  - For the Custom tab, include month/year selects and a small "Apply" button within the tab content.
- [x] Edit `SVD/milk_agency/views_sales_summary.py`:
  - Remove `customer_id` GET parameter processing.
  - Set `customer` to None in context.
  - Remove customer filtering from all querysets (bills_qs, compare_bills_qs, sales_data, compare_sales_data, trend_data).
  - Ensure period-based filtering remains intact for tab functionality.
  - Add logic for 'today' and 'week' periods.
- [x] Convert bar chart to line graph in the template.
- [x] Change line graph to have two lines: one for Milk and one for Curd over time.
- [ ] Test the updated page:
  - Verify tabs switch periods correctly and chart renders for each period.
  - Confirm no customer filter remains.
  - Check for JavaScript errors and ensure chart data matches the selected tab.
