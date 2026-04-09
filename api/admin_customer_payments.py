from django.http import JsonResponse
from django.db.models import Q, F, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view

from milk_agency.models import CustomerPayment


# ==========================================================
#  LIST CUSTOMER PAYMENTS (WITH FILTERS)
# ==========================================================
@api_view(["GET"])
def customer_payments_api(request):

    customer_filter = request.GET.get("customer", "").strip()
    transaction_id_filter = request.GET.get("transaction_id", "").strip()
    status_filter = request.GET.get("status", "").strip()

    payments = CustomerPayment.objects.select_related("customer", "bill").all().order_by("-created_at")

    if customer_filter:
        payments = payments.filter(
            Q(customer__name__icontains=customer_filter)
        )

    if transaction_id_filter:
        payments = payments.filter(transaction_id__icontains=transaction_id_filter)

    if status_filter:
        payments = payments.filter(status__iexact=status_filter)

    total_amount = payments.aggregate(
        total=Coalesce(Sum("amount"), 0)
    )["total"]

    data = []
    for p in payments.values(
        "id",
        "transaction_id",
        "amount",
        "method",
        "status",
        "created_at",
        "bill_id",
        bill_invoice_number=F("bill__invoice_number"),
        customer_name=F("customer__name"),
        customer_id=F("customer_id"),
    ):
        p["created_at"] = p["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        data.append(p)

    return JsonResponse({
        "summary": {
            "count": len(data),
            "total_amount": float(total_amount or 0),
            "success_count": sum(1 for p in data if str(p["status"]).upper() == "SUCCESS"),
            "failed_count": sum(1 for p in data if str(p["status"]).upper() == "FAILED"),
        },
        "count": len(data),
        "payments": data
    })


# ==========================================================
#  UPDATE PAYMENT STATUS
# ==========================================================
@api_view(["POST"])
def update_payment_status_api(request, payment_id):

    payment = get_object_or_404(CustomerPayment, id=payment_id)
    new_status = request.data.get("status")

    if not new_status:
        return JsonResponse({
            "status": "error",
            "message": "status field is required"
        }, status=400)

    payment.status = new_status
    payment.save()

    # 🔴 Recalculate cached due after status change
    customer = payment.customer
    customer.due = customer.get_actual_due()
    customer.save()

    return JsonResponse({
        "status": "success",
        "payment_id": payment.id,
        "new_status": payment.status
    })


# ==========================================================
#  DELETE PAYMENT
# ==========================================================
@api_view(["DELETE"])
def delete_payment_api(request, payment_id):

    payment = get_object_or_404(CustomerPayment, id=payment_id)
    customer = payment.customer  # store before delete

    payment.delete()

    # 🔴 Recalculate cached due after deletion
    customer.due = customer.get_actual_due()
    customer.save()

    return JsonResponse({
        "status": "success",
        "message": f"Payment {payment_id} deleted"
    })
