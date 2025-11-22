import os
from datetime import datetime
from calendar import month_name
from django.conf import settings

from decimal import Decimal
from django.contrib import messages
from .models import Item, BillItem, Customer

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
