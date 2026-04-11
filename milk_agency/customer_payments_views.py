from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models import Sum, DecimalField
from django.db.models.functions import Coalesce
from django.db import transaction

from .models import CustomerPayment
from .paytm import successful_payments_q


def _recalculate_payment_effects(payment):
    if payment.bill_id:
        total_paid = CustomerPayment.objects.filter(
            bill_id=payment.bill_id,
        ).filter(
            successful_payments_q()
        ).aggregate(
            total=Coalesce(
                Sum("amount"),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
        payment.bill.last_paid = total_paid
        payment.bill.save(update_fields=["last_paid"])

    if payment.customer_id:
        payment.customer.due = payment.customer.get_actual_due()
        payment.customer.save(update_fields=["due"])

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


@login_required
def edit_customer_payment(request, pk):
    payment = get_object_or_404(
        CustomerPayment.objects.select_related("customer", "bill"),
        pk=pk,
    )

    if request.method == "POST":
        try:
            payment.amount = Decimal(request.POST.get("amount", "").strip())
            payment.method = (request.POST.get("method") or "").strip()
            payment.status = (request.POST.get("status") or "").strip()

            if payment.amount < 0:
                raise InvalidOperation

            with transaction.atomic():
                payment.save(update_fields=["amount", "method", "status"])
                _recalculate_payment_effects(payment)

            messages.success(request, "Payment updated successfully.")
            return redirect("milk_agency:customer_payments")
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, "Enter a valid payment amount.")

    return render(
        request,
        "milk_agency/edit_customer_payment.html",
        {"payment": payment},
    )


@login_required
def delete_customer_payment(request, pk):
    payment = get_object_or_404(
        CustomerPayment.objects.select_related("customer", "bill"),
        pk=pk,
    )

    if request.method == "POST":
        with transaction.atomic():
            customer = payment.customer
            bill = payment.bill
            payment.delete()

            if bill:
                total_paid = CustomerPayment.objects.filter(
                    bill=bill,
                ).filter(
                    successful_payments_q()
                ).aggregate(
                    total=Coalesce(
                        Sum("amount"),
                        Decimal("0.00"),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                )["total"]
                bill.last_paid = total_paid
                bill.save(update_fields=["last_paid"])

            if customer:
                customer.due = customer.get_actual_due()
                customer.save(update_fields=["due"])

        messages.success(request, "Payment deleted successfully.")
        return redirect("milk_agency:customer_payments")

    return render(
        request,
        "milk_agency/delete_customer_payment.html",
        {"payment": payment},
    )
