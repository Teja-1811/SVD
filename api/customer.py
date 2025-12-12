from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Sum, Avg
from milk_agency.pdf_utils import PDFGenerator
from milk_agency.models import Customer, Bill, Item


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

    # Balance
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
# CUSTOMER ITEMS API
# =======================================================

@api_view(["GET"])
def categories_api(request):
    # Extract all unique categories from Items
    categories = (
        Item.objects.exclude(category__isnull=True)
                    .exclude(category__exact="")
                    .values_list("category", flat=True)
                    .distinct()
    )

    result = []
    for i, cat in enumerate(categories):
        result.append({
            "id": i + 1,
            "name": cat
        })

    return Response(result)

@api_view(["GET"])
def products_api(request):
    category_id = request.GET.get("category_id")

    if not category_id:
        return Response({"error": "category_id is required"}, status=400)

    # Convert category_id back to category name
    categories = (
        Item.objects.exclude(category__isnull=True)
                    .exclude(category__exact="")
                    .values_list("category", flat=True)
                    .distinct()
    )

    try:
        category_index = int(category_id) - 1
        category_name = list(categories)[category_index]
    except:
        return Response({"error": "Invalid category_id"}, status=400)

    # Fetch items belonging to this category
    items = Item.objects.filter(category=category_name, company_id=1)

    product_list = []
    for item in items:
        product_list.append({
            "id": item.id,
            "name": item.name,
            "mrp": float(item.mrp),
            "selling_price": float(item.selling_price),
            "margin": float(item.selling_price - item.buying_price),
            "stock": item.stock_quantity,
            "image": item.image.url if item.image else ""
        })

    return Response(product_list)

@api_view(["GET"])
def customer_invoice_summary_api(request):
    month = request.GET.get("month")
    year = request.GET.get("year")
    customer_id = request.GET.get("customer_id")

    if not (month and year and customer_id):
        return Response({"error": "month, year, and customer_id are required"}, status=400)

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=404)

    # Filter bills
    bills = Bill.objects.filter(
    customer_id=customer_id,
    #invoice_date__year=year,
    #invoice_date__month=month
    )
    
    # Summary calculations
    total_invoices = bills.count()
    total_amount = bills.aggregate(total=Sum("total_amount"))["total"] or 0
    avg_invoice = bills.aggregate(avg=Avg("total_amount"))["avg"] or 0
    latest_invoice_date = bills.order_by("-date").first().date if bills.exists() else None

    data = {
        "total_invoices": total_invoices,
        "total_amount": float(total_amount),
        "latest_invoice": latest_invoice_date.strftime("%Y-%m-%d") if latest_invoice_date else "",
        "avg_invoice": float(avg_invoice)
    }

    return Response(data, status=200)

@api_view(["GET"])
def customer_invoice_list_api(request):
    month = request.GET.get("month")
    year = request.GET.get("year")
    customer_id = request.GET.get("customer_id")

    if not (month and year and customer_id):
        return Response({"error": "month, year, and customer_id are required"}, status=400)

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=404)

    # Filter bills
    bills = Bill.objects.filter(
        customer_id=customer_id,
        date__year=year,
        date__month=month
    ).order_by("-date")

    invoice_list = []

    for bill in bills:
        invoice_list.append({
            "number": bill.invoice_number,
            "date": bill.date.strftime("%Y-%m-%d"),
            "amount": float(bill.total_amount),
        })

    return Response({"invoices": invoice_list}, status=200)

@api_view(["GET"])
def customer_invoice_download_api(request):
    invoice_number = request.GET.get("invoice_number")

    if not invoice_number:
        return Response({"error": "invoice_number is required"}, status=400)

    # Fetch invoice (Bill)
    try:
        bill = Bill.objects.get(invoice_number=invoice_number)
    except Bill.DoesNotExist:
        return Response({"error": "Invoice not found"}, status=404)

    # Use your existing PDF generator utility
    pdf_gen = PDFGenerator()
    return pdf_gen.generate_and_return_pdf(bill, request)
