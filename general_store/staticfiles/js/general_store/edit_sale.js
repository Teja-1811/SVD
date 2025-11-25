document.addEventListener('DOMContentLoaded', function() {
    const addItemBtn = document.getElementById('addItemBtn');
    const saleItems = document.getElementById('saleItems');

    // Add new item
    addItemBtn.addEventListener('click', function() {
        const itemCount = document.querySelectorAll('.sale-item').length;
        const newItem = document.createElement('div');
        newItem.className = 'sale-item row mb-3 align-items-end';
        newItem.innerHTML = `
            <div class="col-md-4">
                <label class="form-label">Product</label>
                <select class="form-select product-select" name="products" required>
                    <option value="">Select Product</option>
                    {% for product in products %}
                    <option value="{{ product.id }}">{{ product.name }} (Stock: {{ product.stock_quantity }})</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-2">
                <label class="form-label">Quantity</label>
                <input type="number" class="form-control quantity-input" name="quantities" min="1" required>
            </div>
            <div class="col-md-2">
                <label class="form-label">Discount</label>
                <input type="number" class="form-control discount-input" name="discounts" min="0" step="0.01">
            </div>
            <div class="col-md-2">
                <label class="form-label">Price per Unit</label>
                <input type="number" class="form-control price-input" readonly>
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-outline-danger remove-item" title="Remove Item">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `;
        saleItems.appendChild(newItem);
        attachEventListeners(newItem);
    });

    // Remove item
    function removeItem(event) {
        if (document.querySelectorAll('.sale-item').length > 1) {
            event.target.closest('.sale-item').remove();
        } else {
            alert('At least one item is required.');
        }
    }

    // Update price when product changes
    function updatePrice(event) {
        const select = event.target;
        const itemDiv = select.closest('.sale-item');
        const priceInput = itemDiv.querySelector('.price-input');
        const selectedOption = select.options[select.selectedIndex];
        if (selectedOption.value) {
            // Extract price from product name or use a default (you may need to adjust this)
            // For now, we'll use a placeholder
            priceInput.value = '0.00'; // Replace with actual price fetching logic
        }
    }

    // Attach event listeners to existing and new items
    function attachEventListeners(item) {
        item.querySelector('.remove-item').addEventListener('click', removeItem);
        item.querySelector('.product-select').addEventListener('change', updatePrice);
    }

    // Attach to existing items
    document.querySelectorAll('.sale-item').forEach(attachEventListeners);
});
