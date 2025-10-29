// Initialize charts when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Sales trend chart
    createSalesTrendChart(
        '{{ sales_labels|safe }}',
        '{{ sales_counts|safe }}',
        '{{ revenue_data|safe }}',
        '{{ profit_data|safe }}'
    );

    // Top products chart
    createTopProductsChart(
        '{{ product_labels|safe }}',
        '{{ product_quantities|safe }}',
        '{{ product_revenues|safe }}'
    );

    // Category revenue chart
    createCategoryChart(
        '{{ category_labels|safe }}',
        '{{ category_data|safe }}'
    );

    // Profit margin chart
    createProfitMarginChart(
        '{{ sales_labels|safe }}',
        '{{ profit_data|safe }}',
        '{{ revenue_data|safe }}'
    );
});
