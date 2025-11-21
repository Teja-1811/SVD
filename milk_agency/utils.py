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
