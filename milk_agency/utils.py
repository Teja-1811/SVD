import os
from datetime import datetime
from calendar import month_name
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from decimal import Decimal, InvalidOperation
from django.contrib import messages
from .models import Item, BillItem, Customer, DailyPayment, MonthlyPaymentSummary, StockInEntry

class InvoicePDFUtils:
    """
    Utility class for managing invoice PDF directory structure
    """

    @staticmethod
    def get_invoice_pdf_directory():
        """
        Get the directory path for saving invoice PDFs based on current date
        Structure: media/year/full month/full date/
        """
        today = datetime.now()
        year_str = today.strftime('%Y')
        month_name_str = month_name[today.month]  # Full month name
        today_date_str = today.strftime('%d-%m-%Y')  # Full date format

        # Create directory path: year/full month/full date
        pdf_dir = os.path.join(
            settings.MEDIA_ROOT,
            year_str,
            month_name_str,
            today_date_str
        )

        # Ensure directory exists
        if not os.path.exists(pdf_dir):
            os.makedirs(pdf_dir, exist_ok=True)

        return pdf_dir

    @staticmethod
    def get_invoice_pdf_path(invoice_number):
        """
        Get the full file path for an invoice PDF
        """
        directory = InvoicePDFUtils.get_invoice_pdf_directory()
        filename = f"{invoice_number}.pdf"
        return os.path.join(directory, filename)

    @staticmethod
    def get_invoice_pdf_url(invoice_number):
        """
        Get the URL path for an invoice PDF
        """
        today = datetime.now()
        year_str = today.strftime('%Y')
        month_name_str = month_name[today.month]  # Full month name
        today_date_str = today.strftime('%d-%m-%Y')  # Full date format

        return f"/media/{year_str}/{month_name_str}/{today_date_str}/{invoice_number}.pdf"

    @staticmethod
    def get_invoice_pdf_relative_path(invoice_number):
        """
        Get the relative path for an invoice PDF
        """
        today = datetime.now()
        year_str = today.strftime('%Y')
        month_name_str = month_name[today.month]  # Full month name
        today_date_str = today.strftime('%d-%m-%Y')  # Full date format

        return f"{year_str}/{month_name_str}/{today_date_str}/{invoice_number}.pdf"

def process_bill_items(bill, item_ids, quantities, discounts):
    total_bill = Decimal(0)
    total_profit = Decimal(0)

    for i, item_id in enumerate(item_ids):
        if item_id and quantities[i]:
            try:
                item = Item.objects.get(id=item_id)
                quantity = int(quantities[i])

                if quantity > 0:
                    price = item.selling_price

                    discount = 0
                    if i < len(discounts) and discounts[i]:
                        try:
                            discount = float(discounts[i])
                        except ValueError:
                            discount = 0

                    total_item_amount = (Decimal(quantity) * price) - (Decimal(discount) * quantity)
                    item_profit = (Decimal(price) - Decimal(item.buying_price)) * Decimal(quantity) - (Decimal(discount) * Decimal(quantity))
                    total_profit += item_profit

                    # Update stock quantity by subtracting the bill quantity (allow negative stock)
                    item.stock_quantity -= quantity
                    item.save()

                    BillItem.objects.create(
                        bill=bill,
                        item=item,
                        quantity=quantity,
                        price_per_unit=price,
                        discount=discount,
                        total_amount=total_item_amount
                    )

                    total_bill += total_item_amount
            except Item.DoesNotExist:
                messages.error(None, f'Item with ID {item_id} not found.')
                raise
            except ValueError:
                messages.error(None, 'Invalid quantity or price.')
                raise

    return total_bill, total_profit


def refresh_monthly_payment_summary(target_date):
    totals = DailyPayment.objects.filter(
        date__year=target_date.year,
        date__month=target_date.month
    ).aggregate(
        total_invoice=Sum("invoice_amount"),
        total_paid=Sum("paid_amount")
    )

    total_invoice = totals["total_invoice"] or Decimal("0")
    total_paid = totals["total_paid"] or Decimal("0")
    total_due = total_invoice - total_paid

    MonthlyPaymentSummary.objects.update_or_create(
        year=target_date.year,
        month=target_date.month,
        defaults={
            "total_invoice": total_invoice,
            "total_paid": total_paid,
            "total_due": total_due,
        }
    )


def parse_decimal(value, default="0"):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def calculate_stock_entry_values(item, crates):
    crates_decimal = parse_decimal(crates)
    pcs_count = parse_decimal(item.pcs_count)
    added_quantity = crates_decimal * pcs_count
    stock_value = added_quantity * parse_decimal(item.buying_price)
    return crates_decimal, added_quantity, stock_value


def recalculate_daily_payment(company_id, target_date):
    if not company_id:
        return

    invoice_total = StockInEntry.objects.filter(
        company_id=company_id,
        date=target_date,
    ).aggregate(total=Sum("value"))["total"] or Decimal("0")

    payment = DailyPayment.objects.filter(company_id=company_id, date=target_date).first()

    if payment:
        payment.invoice_amount = invoice_total
        if invoice_total == Decimal("0") and not payment.paid_amount:
            payment.delete()
        else:
            payment.save(update_fields=["invoice_amount", "updated_at"])
    elif invoice_total > Decimal("0"):
        DailyPayment.objects.create(
            company_id=company_id,
            date=target_date,
            invoice_amount=invoice_total,
            paid_amount=None,
        )


def sync_stock_entry_totals(changes):
    impacted = set()
    for company_id, entry_date in changes:
        if company_id and entry_date:
            impacted.add((company_id, entry_date))

    months = set()
    for company_id, entry_date in impacted:
        recalculate_daily_payment(company_id, entry_date)
        months.add((entry_date.year, entry_date.month, entry_date))

    for _, _, any_date_in_month in months:
        refresh_monthly_payment_summary(any_date_in_month)


def apply_stock_updates(stock_updates, *, entry_date=None):
    target_date = entry_date or timezone.localdate()
    updated_items = []
    impacted_changes = []

    with transaction.atomic():
        for stock_update in stock_updates:
            item = stock_update["item"]
            crates_decimal, added_qty, stock_value = calculate_stock_entry_values(
                item, stock_update.get("crates", 0)
            )
            if crates_decimal <= 0:
                continue

            old_quantity = item.stock_quantity
            item.stock_quantity += int(added_qty)
            item.save(update_fields=["stock_quantity"])

            StockInEntry.objects.create(
                item=item,
                company=item.company,
                date=target_date,
                crates=crates_decimal,
                quantity=added_qty,
                value=stock_value,
            )

            impacted_changes.append((item.company_id, target_date))

            updated_items.append({
                "id": item.id,
                "name": item.name,
                "old_quantity": old_quantity,
                "new_quantity": item.stock_quantity,
                "added_quantity": float(added_qty),
                "difference": float(added_qty),
                "value": float(stock_value),
            })

        if impacted_changes:
            sync_stock_entry_totals(impacted_changes)

    return updated_items


def update_stock_entry(entry, *, crates, date_value):
    previous_company_id = entry.company_id
    previous_date = entry.date

    crates_decimal, added_quantity, stock_value = calculate_stock_entry_values(entry.item, crates)
    quantity_delta = added_quantity - parse_decimal(entry.quantity)

    with transaction.atomic():
        entry.item.stock_quantity += int(quantity_delta)
        entry.item.save(update_fields=["stock_quantity"])

        entry.date = date_value
        entry.company = entry.item.company
        entry.crates = crates_decimal
        entry.quantity = added_quantity
        entry.value = stock_value
        entry.save(update_fields=["date", "company", "crates", "quantity", "value", "updated_at"])

        sync_stock_entry_totals([
            (previous_company_id, previous_date),
            (entry.company_id, entry.date),
        ])

    return entry


def delete_stock_entry(entry):
    impacted_company_id = entry.company_id
    impacted_date = entry.date
    quantity = parse_decimal(entry.quantity)

    with transaction.atomic():
        entry.item.stock_quantity -= int(quantity)
        entry.item.save(update_fields=["stock_quantity"])
        entry.delete()
        sync_stock_entry_totals([(impacted_company_id, impacted_date)])


def calculate_monthly_commissions(year, month):
    """
    Calculate monthly commissions for all commissioned customers for the given month.
    Commissions are calculated for the previous month on the 5th of the current month.
    """
    # Get all customers who are commissioned
    commissioned_customers = Customer.objects.filter(is_commissioned=True)

    for customer in commissioned_customers:
        # Check if commission already exists for this customer and month
        existing_commission = CustomerMonthlyCommission.objects.filter(
            customer=customer,
            year=year,
            month=month
        ).first()

        if existing_commission:
            # Skip if already calculated
            continue

        # Calculate volumes from bills in the specified month
        bills = Bill.objects.filter(
            customer=customer,
            invoice_date__year=year,
            invoice_date__month=month,
        ).prefetch_related('items__item')

        milk_volume = Decimal('0')
        curd_volume = Decimal('0')

        for bill in bills:
            for bill_item in bill.items.all():
                category = bill_item.item.category
                quantity = bill_item.quantity
                if category and quantity:
                    category_lower = category.lower()
                    liters_per_unit = extract_liters_from_name(bill_item.item.name)
                    total_liters = Decimal(str(liters_per_unit)) * Decimal(str(quantity))
                    if category_lower == 'milk':
                        milk_volume += total_liters
                    elif category_lower == 'curd':
                        curd_volume += total_liters

        total_volume = milk_volume + curd_volume

        # Calculate commissions using the same logic as monthly_sales_summary.py
        milk_commission = calculate_milk_commission(milk_volume)
        curd_commission = calculate_curd_commission(curd_volume)
        total_commission = milk_commission + curd_commission

        # Calculate rates
        milk_commission_rate = milk_commission / milk_volume if milk_volume else Decimal('0')
        curd_commission_rate = curd_commission / curd_volume if curd_volume else Decimal('0')

        # Create commission record
        CustomerMonthlyCommission.objects.create(
            customer=customer,
            year=year,
            month=month,
            milk_volume=milk_volume,
            curd_volume=curd_volume,
            total_volume=total_volume,
            milk_commission_rate=milk_commission_rate,
            curd_commission_rate=curd_commission_rate,
            commission_amount=total_commission,
            status=False  # Not yet deducted
        )


def calculate_milk_commission(volume):
    """Calculate commission for milk based on slabs."""
    volume = Decimal(str(volume))
    if volume <= 15:
        return volume * Decimal('0.2')
    elif volume <= 30:
        return Decimal('15') * Decimal('0.2') + (volume - Decimal('15')) * Decimal('0.3')
    else:
        return Decimal('15') * Decimal('0.2') + Decimal('15') * Decimal('0.3') + (volume - Decimal('30')) * Decimal('0.35')


def calculate_curd_commission(volume):
    """Calculate commission for curd based on slabs."""
    volume = Decimal(str(volume))
    if volume <= 20:
        return volume * Decimal('0.25')
    elif volume <= 35:
        return Decimal('20') * Decimal('0.25') + (volume - Decimal('20')) * Decimal('0.35')
    else:
        return Decimal('20') * Decimal('0.25') + Decimal('15') * Decimal('0.35') + (volume - Decimal('35')) * Decimal('0.5')
