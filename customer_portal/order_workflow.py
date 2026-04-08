from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from api.user_bill_pdf_utils import UserPDFGenerator
from milk_agency.models import CustomerPayment
from milk_agency.order_pricing import get_customer_unit_price, get_delivery_charge_amount
from milk_agency.views_bills import generate_bill_from_order

from .models import CustomerOrder


def _recalculate_order_totals(order):
    total_amount = Decimal("0.00")

    for order_item in order.items.select_related("item").all():
        quantity = int(order_item.requested_quantity or 0)
        unit_price = get_customer_unit_price(order_item.item, order.customer)
        discount = Decimal(order_item.discount or 0)
        discount_total = discount * quantity
        line_total = (unit_price * quantity) - discount_total

        order_item.requested_price = unit_price
        order_item.approved_quantity = quantity
        order_item.approved_price = unit_price
        order_item.discount_total = discount_total
        order_item.requested_total = line_total
        order_item.approved_total = line_total
        order_item.save(
            update_fields=[
                "requested_price",
                "approved_quantity",
                "approved_price",
                "discount_total",
                "requested_total",
                "approved_total",
            ]
        )
        total_amount += line_total

    order.delivery_charge = get_delivery_charge_amount(
        customer=order.customer,
        address=order.delivery_address,
    )
    order.total_amount = total_amount
    order.approved_total_amount = total_amount
    order.save(update_fields=["delivery_charge", "total_amount", "approved_total_amount", "updated_at"])
    return total_amount


def _ensure_stock_available(order):
    for order_item in order.items.select_related("item").all():
        item = order_item.item
        if item.stock_quantity < order_item.requested_quantity:
            raise ValueError(f"Only {item.stock_quantity} unit(s) available for {item.name}.")


def finalize_order_after_payment(
    order,
    *,
    payment_reference,
    payment_method="UPI",
    approved_by=None,
    mark_paid=True,
):
    with transaction.atomic():
        locked_order = (
            CustomerOrder.objects.select_for_update()
            .select_related("customer", "bill")
            .prefetch_related("items__item")
            .get(pk=order.pk)
        )

        if locked_order.status in {"cancelled", "rejected"}:
            raise ValueError("This order can no longer be confirmed.")

        if locked_order.payment_reference and locked_order.payment_reference != payment_reference:
            raise ValueError("This order is already linked to a different payment reference.")

        if locked_order.bill_id and locked_order.status == "confirmed":
            existing_payment = CustomerPayment.objects.filter(
                customer=locked_order.customer,
                bill_id=locked_order.bill_id,
                transaction_id=payment_reference,
            ).first()
            return locked_order, locked_order.bill, existing_payment

        _ensure_stock_available(locked_order)
        _recalculate_order_totals(locked_order)

        bill = generate_bill_from_order(locked_order)

        payment = None
        if mark_paid:
            payment_amount = Decimal(bill.total_amount or 0)
            payment, _ = CustomerPayment.objects.get_or_create(
                transaction_id=payment_reference,
                defaults={
                    "customer": locked_order.customer,
                    "bill": bill,
                    "amount": payment_amount,
                    "method": payment_method,
                    "status": "SUCCESS",
                },
            )

            if payment.customer_id != locked_order.customer_id:
                raise ValueError("Payment reference is already used for another customer.")
            if payment.bill_id != bill.id or payment.status != "SUCCESS" or payment.amount != payment_amount:
                payment.bill = bill
                payment.amount = payment_amount
                payment.method = payment_method
                payment.status = "SUCCESS"
                payment.save(update_fields=["bill", "amount", "method", "status"])

            if Decimal(bill.last_paid or 0) != payment_amount:
                bill.last_paid = payment_amount
                bill.save(update_fields=["last_paid"])

        locked_order.status = "confirmed"
        locked_order.approved_by = approved_by
        locked_order.bill = bill
        update_fields = ["status", "approved_by", "bill", "updated_at"]
        if mark_paid:
            locked_order.payment_method = payment_method
            locked_order.payment_status = "success"
            locked_order.payment_reference = payment_reference
            locked_order.payment_confirmed_at = timezone.now()
            update_fields.extend(
                [
                    "payment_method",
                    "payment_status",
                    "payment_reference",
                    "payment_confirmed_at",
                ]
            )
        locked_order.save(update_fields=update_fields)

        if mark_paid:
            locked_order.customer.due = locked_order.customer.get_actual_due()
            locked_order.customer.save(update_fields=["due"])
        UserPDFGenerator().generate_invoice_pdf(bill)

        return locked_order, bill, payment
