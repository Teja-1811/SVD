// Form validation and enhancements
document.getElementById('productForm').addEventListener('submit', function(e) {
    const buyingPrice = parseFloat(document.getElementById('buying_price').value);
    const sellingPrice = parseFloat(document.getElementById('selling_price').value);
    const mrp = parseFloat(document.getElementById('mrp').value);

    if (sellingPrice <= buyingPrice) {
        e.preventDefault();
        alert('Selling price must be greater than buying price.');
        return false;
    }

    if (mrp < sellingPrice) {
        e.preventDefault();
        alert('MRP should not be less than selling price.');
        return false;
    }
});

// Auto-format price inputs
document.querySelectorAll('.price-input').forEach(input => {
    input.addEventListener('blur', function() {
        if (this.value) {
            this.value = parseFloat(this.value).toFixed(2);
        }
    });
});
