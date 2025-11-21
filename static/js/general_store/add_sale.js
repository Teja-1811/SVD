document.addEventListener('DOMContentLoaded', function() {
    const totalAmountInput = document.getElementById('total-amount');
    const billedItemsBody = document.getElementById('billed-items-body');
    const totalQtyEl = document.getElementById('total-qty');
    const totalDiscAmtEl = document.getElementById('total-disc-amt');
    const totalAmtEl = document.getElementById('total-amt');

    function updateTable() {
        // Clear existing rows
        billedItemsBody.innerHTML = '';

        let totalQty = 0;
        let totalDiscAmt = 0;
        let totalAmt = 0;

        // Get all product rows
        document.querySelectorAll('.product-row').forEach(row => {
            const quantity = parseInt(row.querySelector('.quantity-input').value) || 0;
            if (quantity > 0) {
                const productId = row.dataset.productId;
                const name = row.dataset.name;
                const price = parseFloat(row.dataset.price || 0);
                const discount = parseFloat(row.querySelector('.discount-input').value) || 0;
                const discAmt = discount * quantity;
                const itemTotal = (price * quantity) - discAmt;

                // Add row to table
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${name}</td>
                    <td>â‚¹${price.toFixed(2)}</td>
                    <td>${quantity}</td>
                    <td>${discount.toFixed(1)}</td>
                    <td>â‚¹${discAmt.toFixed(2)}</td>
                    <td>â‚¹${itemTotal.toFixed(2)}</td>
                    <td><button type="button" class="btn btn-danger btn-sm delete-item-btn" data-product-id="${productId}">Delete</button></td>
                `;
                billedItemsBody.appendChild(tr);

                // Update totals
                totalQty += quantity;
                totalDiscAmt += discAmt;
                totalAmt += itemTotal;

                // Update hidden inputs
                const qtyHidden = document.querySelector(`.quantity-hidden[data-product-id="${productId}"]`);
                const discHidden = document.querySelector(`.discount-hidden[data-product-id="${productId}"]`);
                if (qtyHidden) qtyHidden.value = quantity;
                if (discHidden) discHidden.value = discount;
            }
        });

        // Update footer totals
        totalQtyEl.textContent = totalQty;
        totalDiscAmtEl.textContent = 'â‚¹' + totalDiscAmt.toFixed(2);
        totalAmtEl.textContent = 'â‚¹' + totalAmt.toFixed(2);
        totalAmountInput.value = 'â‚¹' + totalAmt.toFixed(2);
    }

    // Event listeners for quantity and discount inputs
    document.querySelectorAll('.quantity-input, .discount-input').forEach(input => {
        input.addEventListener('input', function() {
            updateTable();
        });
    });

    document.querySelectorAll('.plus-qty-btn').forEach(button => {
        button.addEventListener('click', function() {
            const row = this.closest('.product-row');
            const qtyInput = row.querySelector('.quantity-input');
            qtyInput.value = parseInt(qtyInput.value) + 1;
            updateTable();
        });
    });

    document.querySelectorAll('.minus-qty-btn').forEach(button => {
        button.addEventListener('click', function() {
            const row = this.closest('.product-row');
            const qtyInput = row.querySelector('.quantity-input');
            if (parseInt(qtyInput.value) > 0) {
                qtyInput.value = parseInt(qtyInput.value) - 1;
                updateTable();
            }
        });
    });

    document.querySelectorAll('.plus-discount-btn').forEach(button => {
        button.addEventListener('click', function() {
            const row = this.closest('.product-row');
            const discountInput = row.querySelector('.discount-input');
            let currentValue = parseFloat(discountInput.value) || 0;
            if (currentValue < 0.1) {
                currentValue = 0;
            }
            discountInput.value = (currentValue + 0.1).toFixed(1);
            updateTable();
        });
    });

    document.querySelectorAll('.minus-discount-btn').forEach(button => {
        button.addEventListener('click', function() {
            const row = this.closest('.product-row');
            const discountInput = row.querySelector('.discount-input');
            let currentValue = parseFloat(discountInput.value) || 0;
            if (currentValue > 0.1) {
                discountInput.value = (currentValue - 0.1).toFixed(1);
                updateTable();
            }
        });
    });

    // Add item to bill functionality
    document.getElementById('add-item-btn').addEventListener('click', function() {
        const itemSelect = document.getElementById('item-select');
        const qtyInput = document.getElementById('add-qty');
        const discInput = document.getElementById('add-disc');

        const productId = itemSelect.value;
        const quantity = parseInt(qtyInput.value) || 0;
        const discount = parseFloat(discInput.value) || 0;

        if (!productId || quantity <= 0) {
            alert('Please select a product and enter a valid quantity.');
            return;
        }

        // Find the corresponding product row and update its inputs
        const productRow = document.querySelector(`.product-row[data-product-id="${productId}"]`);
        if (productRow) {
            const qtyInputEl = productRow.querySelector('.quantity-input');
            const discInputEl = productRow.querySelector('.discount-input');

            qtyInputEl.value = quantity;
            discInputEl.value = discount;

            updateTable();

            // Reset form
            itemSelect.value = '';
            qtyInput.value = '1';
            discInput.value = '0';
        }
    });

    // Delete item functionality
    document.addEventListener('click', function(event) {
        if (event.target.classList.contains('delete-item-btn')) {
            const productId = event.target.dataset.productId;
            const productRow = document.querySelector(`.product-row[data-product-id="${productId}"]`);
            if (productRow) {
                const qtyInputEl = productRow.querySelector('.quantity-input');
                const discInputEl = productRow.querySelector('.discount-input');

                qtyInputEl.value = 0;
                discInputEl.value = 0;

                updateTable();
            }
        }
    });

    // Initial table update
    updateTable();
});
