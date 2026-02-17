from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Avg
from milk_agency.pdf_utils import PDFGenerator
from milk_agency.models import Bill


# =======================================================
# CUSTOMER INVOICE SUMMARY API
# =======================================================
@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def customer_invoice_summary_api(request):
    month = request.GET.get("month")
    year = request.GET.get("year")

    if not (month and year):
        return Response({"error": "month and year are required"}, status=400)

    try:
        month = int(month)
        year = int(year)
    except ValueError:
        return Response({"error": "Invalid month or year"}, status=400)

    customer = request.user

    bills = Bill.objects.filter(
        customer=customer,
        is_deleted=False,
        invoice_date__year=year,
        invoice_date__month=month
    ).order_by("-invoice_date")

    total_invoices = bills.count()
    total_amount = bills.aggregate(total=Sum("total_amount"))["total"] or 0
    avg_invoice = bills.aggregate(avg=Avg("total_amount"))["avg"] or 0
    latest_invoice_date = bills.first().invoice_date if bills.exists() else None

    return Response({
        "total_invoices": total_invoices,
        "total_amount": float(total_amount),
        "latest_invoice": latest_invoice_date.strftime("%Y-%m-%d") if latest_invoice_date else "",
        "avg_invoice": float(avg_invoice)
    }, status=200)


# =======================================================
# CUSTOMER INVOICE LIST API
# =======================================================
@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def customer_invoice_list_api(request):
    month = request.GET.get("month")
    year = request.GET.get("year")

    if not (month and year):
        return Response({"error": "month and year are required"}, status=400)

    try:
        month = int(month)
        year = int(year)
    except ValueError:
        return Response({"error": "Invalid month or year"}, status=400)

    customer = request.user

    bills = Bill.objects.filter(
        customer=customer,
        is_deleted=False,
        invoice_date__year=year,
        invoice_date__month=month
    ).order_by("-invoice_date")

    invoices = [{
        "number": bill.invoice_number,
        "date": bill.invoice_date.strftime("%Y-%m-%d"),
        "amount": float(bill.total_amount)
    } for bill in bills]

    return Response({"invoices": invoices}, status=200)


# =======================================================
# CUSTOMER INVOICE PDF DOWNLOAD API
# =======================================================
@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def customer_invoice_download_api(request):
    invoice_number = request.GET.get("invoice_number")

    if not invoice_number:
        return Response({"error": "invoice_number is required"}, status=400)

    customer = request.user

    try:
        bill = Bill.objects.get(
            invoice_number=invoice_number,
            customer=customer,
            is_deleted=False
        )
    except Bill.DoesNotExist:
        return Response({"error": "Invoice not found"}, status=404)

    pdf_gen = PDFGenerator()
    return pdf_gen.generate_and_return_pdf(bill, request)


# =======================================================
# CUSTOMER INVOICE DETAILS API
# =======================================================
@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def customer_invoice_details_api(request):
    invoice_number = request.GET.get("invoice_number")

    if not invoice_number:
        return Response({"error": "invoice_number is required"}, status=400)

    customer = request.user

    try:
        bill = Bill.objects.get(
            invoice_number=invoice_number,
            customer=customer,
            is_deleted=False
        )
    except Bill.DoesNotExist:
        return Response({"error": "Invoice not found"}, status=404)

    items = [{
        "name": i.item.name,
        "code": i.item.code,
        "price": float(i.price_per_unit),   # ✅ corrected field
        "quantity": i.quantity,
        "discount": float(i.discount),
        "total": float(i.total_amount)      # ✅ corrected field
    } for i in bill.items.all()]

    return Response({
        "invoice_number": bill.invoice_number,
        "invoice_date": bill.invoice_date.strftime("%Y-%m-%d"),
        "customer_name": bill.customer.name,
        "total_amount": float(bill.total_amount),
        "opening_due": float(bill.op_due_amount),
        "last_paid": float(bill.last_paid or 0),
        "items": items,
        "grand_total": float(bill.total_amount),
    }, status=200)
