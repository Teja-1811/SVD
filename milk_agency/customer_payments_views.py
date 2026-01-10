from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import CustomerPayment

@login_required
def customer_payments(request):
    customer_filter = request.GET.get('customer', '').strip()
    transaction_id_filter = request.GET.get('transaction_id', '').strip()

    payments = CustomerPayment.objects.all().order_by('-created_at')

    if customer_filter:
        payments = payments.filter(
            Q(customer__name__icontains=customer_filter) |
            Q(customer__phone__icontains=customer_filter)
        )

    if transaction_id_filter:
        payments = payments.filter(transaction_id__icontains=transaction_id_filter)

    context = {
        'payments': payments,
        'customer_filter': customer_filter,
        'transaction_id_filter': transaction_id_filter,
    }

    return render(request, 'milk_agency/customer_payments.html', context)
