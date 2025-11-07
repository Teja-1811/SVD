# TODO: Add Stock Quantity Display in Bill Generation Template

## Information Gathered
- The bill generation template is located at `SVD/templates/milk_agency/bills/generate_bill.html`.
- Items have a `stock_quantity` field in the `Item` model.
- The template already passes `item.stock_quantity` to the item cards via `data-stock-quantity`.
- The item selection uses a dropdown (`#item-select`) with options that have data attributes.
- When an item is selected, we need to display the available stock quantity.

## Plan
- Modify the HTML structure in `generate_bill.html` to include a display for available quantity.
- Adjust column sizes to accommodate the new field.
- Add `data-stock-quantity` attribute to the dropdown options.
- Add JavaScript to update the available quantity display when an item is selected.

## Dependent Files to be Edited
- `SVD/templates/milk_agency/bills/generate_bill.html`: Update HTML and JavaScript.

## Followup Steps
- Test the bill generation page to ensure stock quantity displays correctly when selecting items.
- Verify that the layout remains responsive.
