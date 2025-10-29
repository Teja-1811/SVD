document.addEventListener('DOMContentLoaded', function() {
    const orderForm = document.getElementById('orderForm');
    const orderSummary = document.getElementById('orderSummary');
    const totalAmount = document.getElementById('totalAmount');

    // Parse items data from Django
    const itemsData = JSON.parse('{{ items_data_json|escapejs }}');

    // Store current selections and quantities to preserve on tab switch
    let savedState = {};

    // Save current state of all item cards
    function saveState() {
        savedState = {};
        document.querySelectorAll('.category-items-container').forEach(container => {
            const company = container.dataset.company;
            const category = container.dataset.category;
            savedState[company] = savedState[company] || {};
            savedState[company][category] = [];
            container.querySelectorAll('.card').forEach(card => {
                const itemId = card.querySelector('.item-id').value;
                const quantity = card.querySelector('.quantity-input').value;
                savedState[company][category].push({itemId, quantity});
            });
        });
    }

    // Restore saved state to item cards
    function restoreState() {
        document.querySelectorAll('.category-items-container').forEach(container => {
            const company = container.dataset.company;
            const category = container.dataset.category;
            if (savedState[company] && savedState[company][category]) {
                const savedItems = savedState[company][category];
                container.querySelectorAll('.card').forEach(card => {
                    const itemId = card.querySelector('.item-id').value;
                    const savedItem = savedItems.find(i => i.itemId === itemId);
                    if (savedItem) {
                        card.querySelector('.quantity-input').value = savedItem.quantity;
                        updateCardTotal(card);
                    }
                });
            }
        });
    }

    // Update total amount for a single card
    function updateCardTotal(card) {
        const quantity = parseInt(card.querySelector('.quantity-input').value) || 0;
        const price = parseFloat(card.querySelector('.item-price').value) || 0;
        const total = quantity * price;
        card.querySelector('.total-amount').textContent = `₹${total.toFixed(2)}`;
    }

    // Update all card totals and order summary
    function updateAllTotals() {
        document.querySelectorAll('.category-items-container .card').forEach(card => {
            updateCardTotal(card);
        });
        updateOrderSummary();
    }

    // Update order summary
    function updateOrderSummary() {
        let total = 0;
        document.querySelectorAll('.category-items-container .card').forEach(card => {
            const quantity = parseInt(card.querySelector('.quantity-input').value) || 0;
            const price = parseFloat(card.querySelector('.item-price').value) || 0;
            total += quantity * price;
        });
        if (total > 0) {
            orderSummary.innerHTML = `<div class="d-flex justify-content-between"><strong>Total:</strong><strong>₹${total.toFixed(2)}</strong></div>`;
        } else {
            orderSummary.innerHTML = '<p class="text-muted">No items selected</p>';
        }
        totalAmount.textContent = `₹${total.toFixed(2)}`;
    }

    // Increment quantity
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('btn-qty-increment')) {
            const input = e.target.closest('.input-group').querySelector('.quantity-input');
            input.value = parseInt(input.value) + 1;
            updateCardTotal(e.target.closest('.card'));
            updateOrderSummary();
        }
    });

    // Decrement quantity
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('btn-qty-decrement')) {
            const input = e.target.closest('.input-group').querySelector('.quantity-input');
            if (parseInt(input.value) > 0) {
                input.value = parseInt(input.value) - 1;
                updateCardTotal(e.target.closest('.card'));
                updateOrderSummary();
            }
        }
    });

    // Quantity input manual change
    document.addEventListener('input', function(e) {
        if (e.target.classList.contains('quantity-input')) {
            if (e.target.value < 0) e.target.value = 0;
            updateCardTotal(e.target.closest('.card'));
            updateOrderSummary();
        }
    });

    // Save state before tab switch
    document.querySelectorAll('#companyTabs button, [id$="-category-tabs"] button').forEach(tabBtn => {
        tabBtn.addEventListener('show.bs.tab', function() {
            saveState();
        });
        tabBtn.addEventListener('shown.bs.tab', function() {
            restoreState();
        });
    });

    // Form submission
    orderForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const items = [];
        document.querySelectorAll('.category-items-container .card').forEach(card => {
            const itemId = card.querySelector('.item-id').value;
            const quantity = parseInt(card.querySelector('.quantity-input').value) || 0;
            const price = parseFloat(card.querySelector('.item-price').value) || 0;
            if (quantity > 0) {
                items.push({
                    item_id: parseInt(itemId),
                    quantity: quantity,
                    price: price
                });
            }
        });

        if (items.length === 0) {
            alert('Please add at least one item to your order.');
            return;
        }

        const formData = new FormData(orderForm);
        const orderData = {
            items: items,
            additional_notes: formData.get('additional_notes') || ''
        };

        fetch('{% url "customer_portal:customer_orders_dashboard" %}', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify(orderData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message + '\nOrder Number: ' + data.order_number);
                location.reload();
            } else {
                // Suppress alert for NOT NULL constraint error on additional_notes
                if (data.message && data.message.includes('NOT NULL constraint failed: customer_portal_customerorder.additional_notes')) {
                    console.error('Backend error: additional_notes cannot be null.');
                } else {
                    alert('Error: ' + data.message);
                }
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
        });
    });

    // Initialize totals on page load
    updateAllTotals();
});
