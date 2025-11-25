// admin_orders_dashboard.js
// clean version — no price needed, only qty + discount

document.addEventListener('DOMContentLoaded', function () {

    // Recalculate card totals on input
    document.querySelectorAll('.quantity-input, .discount-input').forEach(input => {
        input.addEventListener('input', function () {
            const card = this.closest('.card');
            if (card) recalcCardTotal(card);
        });
    });

    // Recalculate totals for all cards on load
    document.querySelectorAll('.card[id^="order-"]').forEach(card => recalcCardTotal(card));
});


function recalcCardTotal(cardElement) {
    let total = 0;

    cardElement.querySelectorAll('table tbody tr').forEach(row => {
        const qty = parseFloat(row.querySelector('.quantity-input')?.value) || 0;
        const discount = parseFloat(row.querySelector('.discount-input')?.value) || 0;

        // Just UI preview (backend does real calculation)
        total += qty - discount;
    });

    const totalEl = cardElement.querySelector('.order-total');
    if (totalEl) totalEl.textContent = total.toFixed(2);
}


function confirmOrder(orderId) {
    if (!confirm('Confirm this order?')) return;

    const card = document.getElementById(`order-${orderId}`);
    if (!card) return alert("Order card not found");

    const updatedItems = [];

    card.querySelectorAll('table tbody tr').forEach(row => {
        const itemId = row.querySelector('.quantity-input')?.dataset.itemId;
        const qty = parseInt(row.querySelector('.quantity-input')?.value) || 0;
        const discount = parseFloat(row.querySelector('.discount-input')?.value) || 0;

        if (itemId) {
            updatedItems.push({
                item_id: itemId,
                quantity: qty,
                discount: discount
            });
        }
    });

    fetch(`/milk_agency/confirm-order/${orderId}/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ quantities: updatedItems })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            if (data.bill_id) {
                window.location.href = `/milk_agency/view-bill/${data.bill_id}/`;
            } else {
                window.location.reload();
            }
        } else {
            alert("Error: " + data.message);
        }
    })
    .catch(err => alert("Error: " + err.message));
}


function rejectOrder(orderId) {
    if (!confirm("Reject this order?")) return;

    fetch(`/milk_agency/reject-order/${orderId}/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
            "Content-Type": "application/json"
        }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            location.reload();
        } else {
            alert("Error: " + data.message);
        }
    })
    .catch(err => alert("Error: " + err.message));
}
