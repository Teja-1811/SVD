from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

from api.user_bill_pdf_utils import UserPDFGenerator, DELIVERY_ITEM_CODE
from milk_agency.models import Bill, BillItem, Customer, Item
from customer_portal.models import CustomerOrder

DELIVERY_CHARGE_AMOUNT = Decimal("10")


def _unit_price(item, customer):
    """Use selling price for retailers and MRP for direct users."""
    if customer and getattr(customer, "user_type", "").lower() == "user":
        return Decimal(item.mrp or item.selling_price)
    return Decimal(item.selling_price)


def _is_delivery_mode(request_data):
    mode = str(
        request_data.get("delivery_mode")
        or request_data.get("delivery_type")
        or request_data.get("delivery")
        or "takeaway"
    ).lower()
    return mode in ("delivery", "delivered", "home_delivery", "home-delivery")

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
            "due": str(c.due)  # cached value (fast UI)
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

    bills = Bill.objects.filter(is_deleted=False).select_related("customer").order_by('-invoice_date', '-id')

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
        Bill.objects.filter(is_deleted=False).select_related('customer'),
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
    invoice_date = request.data.get("invoice_date")
    is_delivery = _is_delivery_mode(request.data)

    customer = Customer.objects.filter(id=customer_id).first()

    try:
        bill_date = datetime.strptime(invoice_date, "%Y-%m-%d").date() if invoice_date else timezone.localdate()
    except ValueError:
        return Response({"success": False, "message": "Invalid invoice_date"}, status=400)

    with transaction.atomic():

        bill = Bill.objects.create(
            customer=customer,
            invoice_number=f"INV-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            invoice_date=bill_date,
            total_amount=Decimal(0),
            op_due_amount=customer.due if customer else 0,
            last_paid=Decimal(0),
            profit=Decimal(0)
        )

        total = Decimal(0)
        total_profit = Decimal(0)

        for i, item_id in enumerate(item_ids):
            item = Item.objects.get(id=item_id)

            qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
            discount = Decimal(discounts[i]) if (discounts and i < len(discounts) and discounts[i]) else Decimal(0)
            if qty <= 0:
                continue

            unit_price = _unit_price(item, customer)

            line_total = (unit_price * qty) - (discount * qty)
            profit = ((unit_price - item.buying_price) * qty) - (discount * qty)

            BillItem.objects.create(
                bill=bill,
                item=item,
                price_per_unit=unit_price,
                discount=discount,
                quantity=qty,
                total_amount=line_total
            )

            item.stock_quantity -= qty
            item.save()

            total += line_total
            total_profit += profit

        if is_delivery and customer and getattr(customer, "user_type", "").lower() == "user":
            delivery_item, _ = Item.objects.get_or_create(
                code=DELIVERY_ITEM_CODE,
                defaults={
                    "name": "Delivery Charge",
                    "selling_price": DELIVERY_CHARGE_AMOUNT,
                    "buying_price": Decimal(0),
                    "mrp": DELIVERY_CHARGE_AMOUNT,
                    "stock_quantity": 0,
                },
            )
            BillItem.objects.create(
                bill=bill,
                item=delivery_item,
                price_per_unit=DELIVERY_CHARGE_AMOUNT,
                discount=Decimal(0),
                quantity=1,
                total_amount=DELIVERY_CHARGE_AMOUNT,
            )
            total += DELIVERY_CHARGE_AMOUNT
            total_profit += DELIVERY_CHARGE_AMOUNT

        bill.total_amount = total
        bill.profit = total_profit
        bill.save()

        if customer:
            customer.due = customer.get_actual_due()
            customer.save()

    return Response({"success": True, "bill_id": bill.id})


# ------------------------------------------
# 6️⃣ EDIT BILL
# ------------------------------------------
@api_view(['POST'])
def api_edit_bill(request, bill_id):

    bill = get_object_or_404(Bill, id=bill_id)
    old_total = bill.total_amount  # store before changes

    new_customer_id = request.data.get("customer")
    new_customer = Customer.objects.filter(id=new_customer_id).first() if new_customer_id else None
    item_ids = request.data.get("items", [])
    quantities = request.data.get("quantities", [])
    discounts = request.data.get("discounts", [])
    invoice_date = request.data.get("invoice_date")
    is_delivery = _is_delivery_mode(request.data)

    bill_items = BillItem.objects.filter(bill=bill)

    with transaction.atomic():

        if invoice_date:
            bill.invoice_date = datetime.strptime(invoice_date, "%Y-%m-%d").date()

        # restore stock
        for bi in bill_items:
            bi.item.stock_quantity += bi.quantity
            bi.item.save()

        bill_items.delete()

        total = Decimal(0)
        total_profit = Decimal(0)

        for i, item_id in enumerate(item_ids):
            item = Item.objects.get(id=item_id)
            qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
            discount = Decimal(discounts[i]) if (discounts and i < len(discounts) and discounts[i]) else Decimal(0)

            if qty <= 0:
                continue

            unit_price = _unit_price(item, new_customer or bill.customer)

            line_total = (unit_price * qty) - (discount * qty)
            profit = ((unit_price - item.buying_price) * qty) - (discount * qty)

            BillItem.objects.create(
                bill=bill,
                item=item,
                price_per_unit=unit_price,
                discount=discount,
                quantity=qty,
                total_amount=line_total
            )

            item.stock_quantity -= qty
            item.save()

            total += line_total
            total_profit += profit

        if is_delivery and new_customer and getattr(new_customer, "user_type", "").lower() == "user":
            delivery_item, _ = Item.objects.get_or_create(
                code=DELIVERY_ITEM_CODE,
                defaults={
                    "name": "Delivery Charge",
                    "selling_price": DELIVERY_CHARGE_AMOUNT,
                    "buying_price": Decimal(0),
                    "mrp": DELIVERY_CHARGE_AMOUNT,
                    "stock_quantity": 0,
                },
            )
            BillItem.objects.create(
                bill=bill,
                item=delivery_item,
                price_per_unit=DELIVERY_CHARGE_AMOUNT,
                discount=Decimal(0),
                quantity=1,
                total_amount=DELIVERY_CHARGE_AMOUNT,
            )
            total += DELIVERY_CHARGE_AMOUNT
            total_profit += DELIVERY_CHARGE_AMOUNT

        old_customer = bill.customer

        bill.customer = new_customer
        bill.op_due_amount = new_customer.due if new_customer else Decimal(0)
        bill.total_amount = total
        bill.profit = total_profit
        bill.save()

        # refresh due cache safely
        if old_customer:
            old_customer.due = old_customer.get_actual_due()
            old_customer.save()

        if new_customer and new_customer != old_customer:
            new_customer.due = new_customer.get_actual_due()
            new_customer.save()

    return Response({"success": True})


# ------------------------------------------
# 7️⃣ DELETE BILL (soft delete + rollback)
# ------------------------------------------
@api_view(['DELETE'])
def api_delete_bill(request, bill_id):

    bill = get_object_or_404(Bill, id=bill_id)
    bill_items = BillItem.objects.filter(bill=bill)

    with transaction.atomic():

        for bi in bill_items:
            bi.item.stock_quantity += bi.quantity
            bi.item.save()

        bill_items.delete()
        bill.is_deleted = True
        bill.save(update_fields=["is_deleted"])

        if bill.customer:
            bill.customer.due = bill.customer.get_actual_due()
            bill.customer.save()

    return Response({"success": True})


@api_view(['GET'])
def api_download_bill(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    pdf_generator = UserPDFGenerator()
    return pdf_generator.generate_and_return_pdf(bill, request)
