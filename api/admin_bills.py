from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
from milk_agency.views_bills import generate_invoice_pdf

from milk_agency.models import Bill, BillItem, Customer, Item

from customer_portal.models import CustomerOrder


# ------------------------------------------
# 1️⃣ GET CUSTOMERS
# ------------------------------------------
@api_view(['GET'])
def api_get_customers(request):
    customers = Customer.objects.filter(frozen=False).order_by("name")

    return Response([
        {
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
            "area": c.area or "",
            "due": str(c.due)
        }
        for c in customers
    ])


# ------------------------------------------
# 2️⃣ BILLS DASHBOARD (filters + pagination)
# ------------------------------------------
@api_view(['GET'])
def api_list_bills(request):

    customer_id = request.GET.get("customer")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    page = request.GET.get("page", 1)

    bills = Bill.objects.select_related("customer").order_by('-invoice_date', '-id')

    if customer_id:
        bills = bills.filter(customer_id=customer_id)

    if start_date:
        bills = bills.filter(invoice_date__gte=start_date)

    if end_date:
        bills = bills.filter(invoice_date__lte=end_date)

    paginator = Paginator(bills, 25)
    page_obj = paginator.get_page(page)

    data = []
    for b in page_obj:
        data.append({
            "id": b.id,
            "invoice_number": b.invoice_number,
            "invoice_date": str(b.invoice_date),
            "customer": b.customer.name if b.customer else "Anonymous",
            "total_amount": str(b.total_amount),
            "op_due": str(b.op_due_amount),
            "current_due": str(b.customer.due) if b.customer else "0",
            "profit": str(b.profit)
        })

    return Response({
        "results": data,
        "current_page": page_obj.number,
        "total_pages": paginator.num_pages,
        "total_records": paginator.count
    })


# ------------------------------------------
# 3️⃣ BILL DETAILS
# ------------------------------------------
@api_view(['GET'])
def api_bill_detail(request, bill_id):

    bill = get_object_or_404(
        Bill.objects.select_related('customer'),
        id=bill_id
    )

    return Response({
        "id": bill.id,
        "invoice_number": bill.invoice_number,
        "invoice_date": str(bill.invoice_date),
        "customer": bill.customer.name if bill.customer else None,
        "total_amount": float(bill.total_amount),
        "op_due_amount": float(bill.op_due_amount),
        "last_paid": float(bill.last_paid),
        "current_due": float(bill.customer.due if bill.customer else 0),
        "profit": float(bill.profit)
    })


# ------------------------------------------
# 4️⃣ BILL ITEMS
# ------------------------------------------
@api_view(['GET'])
def api_bill_items(request, bill_id):

    items = BillItem.objects.filter(bill_id=bill_id).select_related("item")

    return Response([
        {
            "item_name": i.item.name,
            "quantity": i.quantity,
            "price_per_unit": float(i.price_per_unit),
            "discount": float(i.discount),
            "total_discount": float(i.discount * i.quantity),
            "total_amount": float(i.total_amount)
        }
        for i in items
    ])


# ------------------------------------------
# 5️⃣ CREATE BILL (manual entry)
# ------------------------------------------
@api_view(['POST'])
def api_create_bill(request):

    customer_id = request.data.get("customer")
    item_ids = request.data.get("items", [])
    quantities = request.data.get("quantities", [])
    discounts = request.data.get("discounts", [])

    customer = Customer.objects.filter(id=customer_id).first()

    with transaction.atomic():

        bill = Bill.objects.create(
            customer=customer,
            invoice_number=f"INV-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            total_amount=Decimal(0),
            op_due_amount=customer.due if customer else 0,
            last_paid=Decimal(0),
            profit=Decimal(0)
        )

        total = Decimal(0)
        total_profit = Decimal(0)

        for i, item_id in enumerate(item_ids):

            item = Item.objects.get(id=item_id)

            qty = int(quantities[i])
            discount = Decimal(discounts[i]) if discounts else Decimal(0)

            line_total = (item.selling_price * qty) - (discount * qty)
            profit = ((item.selling_price - item.buying_price) * qty) - (discount * qty)

            BillItem.objects.create(
                bill=bill,
                item=item,
                price_per_unit=item.selling_price,
                discount=discount,
                quantity=qty,
                total_amount=line_total
            )

            item.stock_quantity -= qty
            item.save()

            total += line_total
            total_profit += profit

        bill.total_amount = total
        bill.profit = total_profit
        bill.save()

        if customer:
            customer.due = bill.op_due_amount + total
            customer.save()

    return Response({"success": True, "bill_id": bill.id})


# ------------------------------------------
# 6️⃣ EDIT BILL
# ------------------------------------------
@api_view(['POST'])
def api_edit_bill(request, bill_id):

    bill = get_object_or_404(Bill, id=bill_id)

    item_ids = request.data.get("items", [])
    quantities = request.data.get("quantities", [])
    discounts = request.data.get("discounts", [])

    bill_items = BillItem.objects.filter(bill=bill)

    with transaction.atomic():

        # restore stock
        for bi in bill_items:
            bi.item.stock_quantity += bi.quantity
            bi.item.save()

        bill_items.delete()

        total = Decimal(0)
        total_profit = Decimal(0)

        for i, item_id in enumerate(item_ids):

            item = Item.objects.get(id=item_id)

            qty = int(quantities[i])
            discount = Decimal(discounts[i])

            line_total = (item.selling_price * qty) - (discount * qty)
            profit = ((item.selling_price - item.buying_price) * qty) - (discount * qty)

            BillItem.objects.create(
                bill=bill,
                item=item,
                price_per_unit=item.selling_price,
                discount=discount,
                quantity=qty,
                total_amount=line_total
            )

            item.stock_quantity -= qty
            item.save()

            total += line_total
            total_profit += profit

        bill.total_amount = total
        bill.profit = total_profit
        bill.save()

        if bill.customer:
            bill.customer.due = bill.op_due_amount + total
            bill.customer.save()

    return Response({"success": True})


# ------------------------------------------
# 7️⃣ DELETE BILL (safe rollback)
# ------------------------------------------
@api_view(['DELETE'])
def api_delete_bill(request, bill_id):

    bill = get_object_or_404(Bill, id=bill_id)
    bill_items = BillItem.objects.filter(bill=bill)

    with transaction.atomic():

        # Return stock
        for bi in bill_items:
            bi.item.stock_quantity += bi.quantity
            bi.item.save()

        # Adjust due
        if bill.customer:
            bill.customer.due -= bill.total_amount
            bill.customer.save()

        bill_items.delete()
        bill.delete()

    return Response({"success": True})

@api_view(['GET'])
def api_download_bill(request, bill_id):
    return generate_invoice_pdf(request, bill_id)
