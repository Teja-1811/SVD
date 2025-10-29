function updateDateTime() {
    const now = new Date();
    // No date/time display needed for trends page
}

document.addEventListener('DOMContentLoaded', function() {
    // Sales trend chart
    createSalesTrendChart(
        {{ labels|safe }},
        {{ sales_counts|safe }},
        {{ revenue_data|safe }},
        {{ profit_data|safe }}
    );

    // Top products chart
    createTopProductsChart(
        {{ product_labels|safe }},
        {{ product_quantities|safe }},
        {{ product_revenues|safe }}
    );

    // Revenue vs Profit chart
    createRevenueProfitChart(
        {{ labels|safe }},
        {{ revenue_data|safe }},
        {{ profit_data|safe }}
    );

    // Profit margin chart
    createProfitMarginChart(
        {{ labels|safe }},
        {{ profit_data|safe }},
        {{ revenue_data|safe }}
    );
});

// Function to create revenue vs profit chart
function createRevenueProfitChart(labels, revenueData, profitData) {
    const ctx = document.getElementById('revenueProfitChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Revenue (₹)',
                data: revenueData,
                backgroundColor: 'rgba(54, 162, 235, 0.8)',
                borderColor: 'rgb(54, 162, 235)',
                borderWidth: 1
            }, {
                label: 'Profit (₹)',
                data: profitData,
                backgroundColor: 'rgba(255, 99, 132, 0.8)',
                borderColor: 'rgb(255, 99, 132)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Revenue vs Profit Comparison'
                },
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Period'
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Amount (₹)'
                    }
                }
            }
        }
    });
}

// Category filter functionality
document.getElementById('categoryFilter').addEventListener('change', function() {
    const categoryId = this.value;
    const currentUrl = new URL(window.location);
    if (categoryId) {
        currentUrl.searchParams.set('category', categoryId);
    } else {
        currentUrl.searchParams.delete('category');
    }
    window.location.href = currentUrl.toString();
});
