// Function to recalculate totals when quantity changes
function recalculateTotals(cardElement) {
    const quantityInputs = cardElement.querySelectorAll('.quantity-input');
    let orderTotal = 0;

    quantityInputs.forEach(input => {
        const quantity = parseFloat(input.value) || 0;
        const priceText = input.closest('tr').querySelector('td:nth-child(3)').textContent;
        const price = parseFloat(priceText.replace('₹', '').replace(',', '')) || 0;
        const itemTotal = quantity * price;

        // Update item total display
        const itemTotalCell = input.closest('tr').querySelector('.item-total');
        itemTotalCell.textContent = '₹' + itemTotal.toFixed(2);

        orderTotal += itemTotal;
    });

    // Update order total display
    const orderTotalElement = cardElement.querySelector('.card-body .row.mb-3 .col-sm-6:last-child strong');
    if (orderTotalElement && orderTotalElement.textContent.includes('Total Amount:')) {
        const totalAmountCell = orderTotalElement.nextElementSibling;
        totalAmountCell.textContent = '₹' + orderTotal.toFixed(2);
    }
}

// Add event listeners to quantity inputs
document.addEventListener('DOMContentLoaded', function() {
    const quantityInputs = document.querySelectorAll('.quantity-input');
    quantityInputs.forEach(input => {
        input.addEventListener('input', function() {
            const cardElement = this.closest('.card');
            recalculateTotals(cardElement);
        });
    });
});

function confirmOrder(orderId) {
    if (confirm('Are you sure you want to confirm this order?')) {
        // Collect updated quantities
        const cardElement = document.getElementById(`order-${orderId}`);
        if (!cardElement) {
            alert('Order card not found.');
            return;
        }
        const quantityInputs = cardElement.querySelectorAll('.quantity-input');
        let updatedQuantities = [];
        quantityInputs.forEach(input => {
            updatedQuantities.push({
                item_id: input.getAttribute('data-item-id'),
                quantity: parseInt(input.value)
            });
        });

        fetch(`/milk_agency/confirm-order/${orderId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ quantities: updatedQuantities })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                alert(data.message);
                // Redirect to reports dashboard to view the generated invoice
                window.location.href = '/milk_agency/admin-orders-dashboard/';
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
        });
    }
}

function rejectOrder(orderId) {
    if (confirm('Are you sure you want to reject this order?')) {
        fetch(`/milk_agency/reject-order/${orderId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                alert(data.message);
                location.reload();
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
        });
    }
}
