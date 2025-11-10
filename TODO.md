# TODO: Improve Update Stock Page Usability

## Overview
Enhance the update-stock page (http://127.0.0.1:8000/milk_agency/update-stock/) to make it easier to use by adding search functionality, clear all button, live preview, select all per category, better mobile responsiveness, and tooltips.

## Steps to Complete

### 1. Add Search Bar
- Add a search input field above the company filter.
- Implement JavaScript to filter table rows based on item name as the user types.
- Make it case-insensitive and highlight matching text.

### 2. Add Clear All Button
- Add a "Clear All" button next to the Update Stock button.
- Implement JavaScript to reset all crate input fields to 0.

### 3. Show Live Preview of New Stock Quantities
- For each row, add a column or span to show the calculated new quantity (current + crates * units per crate).
- Update this preview in real-time as the user changes the crate input.
- Use JavaScript to listen for input changes and recalculate.

### 4. Add Select All Feature per Category
- For each category section, add a "Set All Crates" input and button.
- Allow setting the same number of crates for all items in that category.
- Implement JavaScript to apply the value to all inputs in the category.

### 5. Improve Mobile Responsiveness
- Adjust table layout for smaller screens (e.g., stack columns or make inputs larger).
- Ensure buttons and filters are touch-friendly.
- Update CSS classes for better mobile display.

### 6. Add Tooltips for Better Guidance
- Add tooltips to input fields explaining what to enter (e.g., "Enter number of crates to add").
- Use Bootstrap tooltips or similar for hover/click info.
- Add help text for the search and select all features.

### 7. Test the Changes
- Load the page and test all new features.
- Verify on different screen sizes.
- Ensure no JavaScript errors and functionality works as expected.

## Files to Edit
- SVD/templates/milk_agency/stock/update_stock.html (main template)
- SVD/static/css/milk_agency/update_stock.css (if needed for responsiveness)

## Notes
- All changes are frontend-only; no backend modifications required.
- Use existing Bootstrap classes where possible for consistency.
