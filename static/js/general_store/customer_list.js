// Search functionality
document.getElementById('searchInput').addEventListener('keyup', function() {
    const filter = this.value.toLowerCase();
    const rows = document.querySelectorAll('.customer-row');

    rows.forEach(row => {
        const name = row.cells[0].textContent.toLowerCase();
        const phone = row.cells[1].textContent.toLowerCase();
        const address = row.cells[2].textContent.toLowerCase();

        if (name.includes(filter) || phone.includes(filter) || address.includes(filter)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
});

// View customer details (placeholder for future enhancement)
function viewCustomer(customerId) {
    // For now, just redirect to edit page
    window.location.href = `/general_store/customers/${customerId}/edit/`;
}
