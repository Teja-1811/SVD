document.addEventListener('DOMContentLoaded', function() {
    const filterForm = document.getElementById('filterForm');
    const customerSelect = document.getElementById('customer');

    // Function to submit form automatically
    function autoSubmit() {
        filterForm.submit();
    }

    // Add event listeners for auto-submit
    customerSelect.addEventListener('change', autoSubmit);
});

function confirmDelete(saleId) {
    const deleteLink = document.getElementById('deleteLink');
    deleteLink.href = "{% url 'general_store:delete_sale' 0 %}".replace('0', saleId);
    const modal = new bootstrap.Modal(document.getElementById('deleteModal'));
    modal.show();
}
