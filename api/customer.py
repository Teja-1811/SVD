from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Sum, Avg
from milk_agency.pdf_utils import PDFGenerator
from milk_agency.models import Customer, Bill


# =======================================================
# CUSTOMER DASHBOARD API
# =======================================================
@api_view(["GET"])
def customer_dashboard_api(request):
    user_id = request.GET.get("user_id")

    if not user_id:
        return Response({"error": "user_id is required"}, status=400)

    try:
        customer = Customer.objects.get(id=user_id)
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=404)

    balance = customer.due or 0

    data = {
        "customerName": customer.name,
        "balance": float(balance),
        "shopName": customer.shop_name or "",
        "phone": customer.phone,
        "accountStatus": "Active" if customer.is_active else "Inactive",
    }

    return Response(data, status=200)


# =======================================================
# CUSTOMER INVOICE SUMMARY API
# =======================================================
@api_view(["GET"])
def customer_invoice_summary_api(request):
    month = request.GET.get("month")
    year = request.GET.get("year")
    customer_id = request.GET.get("customer_id")

    if not (month and year and customer_id):
        return Response({"error": "month, year, and customer_id are required"}, status=400)

    try:
        Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=404)

    # MUST USE invoice_date (same as web portal)
    bills = Bill.objects.filter(
        customer_id=customer_id,
        invoice_date__year=year,
        invoice_date__month=month
    ).order_by("-invoice_date")

    total_invoices = bills.count()
    total_amount = bills.aggregate(total=Sum("total_amount"))["total"] or 0
    avg_invoice = bills.aggregate(avg=Avg("total_amount"))["avg"] or 0
    latest_invoice_date = bills.first().invoice_date if bills.exists() else None

    data = {
        "total_invoices": total_invoices,
        "total_amount": float(total_amount),
        "latest_invoice": latest_invoice_date.strftime("%Y-%m-%d") if latest_invoice_date else "",
        "avg_invoice": float(avg_invoice)
    }

    return Response(data, status=200)

# =======================================================
# CUSTOMER INVOICE LIST API
# =======================================================
@api_view(["GET"])
def customer_invoice_list_api(request):
    month = request.GET.get("month")
    year = request.GET.get("year")
    customer_id = request.GET.get("customer_id")

    if not (month and year and customer_id):
        return Response({"error": "month, year, and customer_id are required"}, status=400)

    try:
        Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=404)

    bills = Bill.objects.filter(
        customer_id=customer_id,
        invoice_date__year=year,
        invoice_date__month=month
    ).order_by("-invoice_date")

    invoice_list = [
        {
            "number": bill.invoice_number,
            "date": bill.invoice_date.strftime("%Y-%m-%d"),
            "amount": float(bill.total_amount),
        }
        for bill in bills
    ]

    return Response({"invoices": invoice_list}, status=200)


# =======================================================
# CUSTOMER INVOICE PDF DOWNLOAD API
# =======================================================
@api_view(["GET"])
def customer_invoice_download_api(request):
    invoice_number = request.GET.get("invoice_number")

    if not invoice_number:
        return Response({"error": "invoice_number is required"}, status=400)

    try:
        bill = Bill.objects.get(invoice_number=invoice_number)
    except Bill.DoesNotExist:
        return Response({"error": "Invoice not found"}, status=404)

    pdf_gen = PDFGenerator()
    return pdf_gen.generate_and_return_pdf(bill, request)

#======================================================
# CUSTOMER INVOICE DETAILS API
# =======================================================
@api_view(["GET"])
def customer_invoice_details_api(request):
    invoice_number = request.GET.get("invoice_number")

    if not invoice_number:
        return Response({"error": "invoice_number is required"}, status=400)

    try:
        bill = Bill.objects.get(invoice_number=invoice_number)
    except Bill.DoesNotExist:
        return Response({"error": "Invoice not found"}, status=404)

    items = []
    for item in bill.items.all():
        items.append({
            "name": item.item.name,
            "code": item.item.code,
            "price": float(item.price),
            "quantity": item.quantity,
            "discount": float(item.discount),
            "total": float(item.total)
        })

    data = {
        "invoice_number": bill.invoice_number,
        "invoice_date": bill.invoice_date.strftime("%Y-%m-%d"),
        "customer_name": bill.customer.name,
        "total_amount": float(bill.total_amount),
        "opening_due": float(bill.op_due_amount),
        "last_paid": float(bill.last_paid or 0),
        "items": items,
        "grand_total": float(bill.total_amount),
    }

    return Response(data, status=200)
