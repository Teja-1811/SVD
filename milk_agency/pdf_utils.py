import os
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from num2words import num2words
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.conf import settings
from .models import BillItem
from .utils import InvoicePDFUtils

class PDFGenerator:
    """Optimized PDF generation utility"""

    def __init__(self):
        self.width, self.height = letter

    def generate_invoice_pdf(self, bill):
        """Generate invoice PDF and save to file system"""
        bill_items = BillItem.objects.filter(bill=bill).select_related('item')

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        self._draw_invoice_template(c, bill, bill_items)

        # Save PDF
        pdf = buffer.getvalue()
        pdf_path = InvoicePDFUtils.get_invoice_pdf_path(bill.invoice_number)

        pdf_dir = os.path.dirname(pdf_path)
        os.makedirs(pdf_dir, exist_ok=True)

        with open(pdf_path, 'wb') as f:
            f.write(pdf)

        buffer.close()
        return pdf_path

    def generate_and_return_pdf(self, bill, request=None):
        """Generate PDF and return as HTTP response"""
        bill_items = BillItem.objects.filter(bill=bill).select_related('item')

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        self._draw_invoice_template(c, bill, bill_items)

        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename=invoice_{bill.invoice_number}.pdf'
        response.write(pdf)

        return response

    def _draw_invoice_template(self, c, bill, bill_items):
        """Draw the complete invoice template"""
        width, height = self.width, self.height

        # Draw border
        margin = 30
        c.setLineWidth(2)
        c.setStrokeColorRGB(0.8, 0, 0)
        c.setTitle(f"Invoice - {bill.invoice_number}")
        c.rect(margin, margin, width - 2*margin, height - 2*margin)

        # Draw company header
        self._draw_company_header(c, width, height)

        # Draw customer details
        y_pos = self._draw_customer_details(c, bill, width, height)

        # Draw items table
        y_pos = self._draw_items_table(c, bill_items, width, y_pos)

        # Draw totals
        y_pos = self._draw_totals(c, bill, width, y_pos)

        # Draw signature only (stamps removed)
        self._draw_stamp_and_signature(c, width, height)

        # Draw footer
        self._draw_footer(c, width, height)

        c.save()

    def _draw_company_header(self, c, width, height):
        """Draw company header section"""
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, height - 50, "Sri Vijaya Durga Milk Agencies")
        c.setFont("Helvetica", 10)
        c.drawString(40, height - 65, "Near Santa Market, Main Road")
        c.drawString(40, height - 80, "Gundugolanu, Bhimadolu, Eluru, AP - 534427")
        c.drawString(40, height - 95, "Phone: 9392890375")

        # --- LOGO ---
        # static/images/SVD1.png
        logo_path = os.path.join(settings.BASE_DIR, "static", "images", "SVD1.png")
        if os.path.exists(logo_path):
            try:
                logo = ImageReader(logo_path)
                c.drawImage(logo, 280, height - 110, width=80, height=80, mask='auto')
            except Exception as e:
                # optional: print(e) or log
                pass


    def _draw_customer_details(self, c, bill, width, height):
        """Draw customer details section"""
        # Invoice details
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(width - 40, height - 50, f"Invoice No. {bill.invoice_number}")
        c.setFont("Helvetica", 10)
        c.drawRightString(width - 40, height - 65, f"Invoice Date: {bill.invoice_date.strftime('%d %b %Y')}")

        # Customer box
        box_x, box_y = 40, height - 220
        box_width, box_height = width - 80, 100

        c.setStrokeColorRGB(0.8, 0, 0)
        c.setLineWidth(1)
        c.roundRect(box_x, box_y, box_width, box_height, 10, stroke=1, fill=0)

        c.setFont("Helvetica-Bold", 12)
        c.drawString(box_x + 10, box_y + box_height - 20, "Bill and Ship To")
        c.setFont("Helvetica-Bold", 10)
        c.drawString(box_x + 10, box_y + box_height - 40, bill.customer.name)
        c.setFont("Helvetica", 10)
        address = bill.customer.flat_number + ", " + bill.customer.area + ", " + bill.customer.city + ", " + bill.customer.state + " - " + bill.customer.pin_code
        if bill.customer.shop_name:
            c.drawString(box_x + 10, box_y + box_height - 55, f"Shop: {bill.customer.shop_name}")
            c.drawString(box_x + 10, box_y + box_height - 70, f"Address : {address}")
            c.drawString(box_x + 10, box_y + box_height - 85, f"Phone: {bill.customer.phone or ''}")
        else:
            c.drawString(box_x + 10, box_y + box_height - 55, bill.customer.area or "")
            c.drawString(box_x + 10, box_y + box_height - 70, f"Phone: {bill.customer.phone or ''}")

        return box_y - 20

    def _draw_items_table(self, c, bill_items, width, start_y):
        """Draw items table with calculations"""
        y = start_y

        # Headers
        c.setFont("Helvetica-Bold", 10)
        headers = ["#", "Item Details", "MRP", "Price/Unit", "Disc./Unit", "Qty", "Rate", "Total"]
        x_positions = [50, 70, 230, 270, 350, 420, 470, 530]

        for i, header in enumerate(headers):
            c.drawString(x_positions[i], y, header)

        y -= 8
        c.line(40, y, width - 40, y)
        y -= 15

        # Items
        c.setFont("Helvetica", 10)
        total_discount = Decimal('0')
        total_quantity = 0
        total_rate = Decimal('0')
        total_amount = Decimal('0')

        for idx, item in enumerate(bill_items, start=1):
            rate = item.price_per_unit - item.discount
            c.drawString(x_positions[0], y, f"{idx:02d}")
            c.drawString(x_positions[1], y, item.item.name)
            c.drawString(x_positions[2], y, f"{item.item.mrp:.2f}")
            c.drawString(x_positions[3], y, f"{item.price_per_unit:.2f}")

            if item.discount > 0:
                discount_percent = (item.discount / item.price_per_unit) * 100 if item.price_per_unit else 0
                c.drawString(x_positions[4], y, f"{item.discount:.2f} ({discount_percent:.2f}%)")
            else:
                c.drawString(x_positions[4], y, "-")

            c.drawString(x_positions[5], y, str(item.quantity))
            c.drawString(x_positions[6], y, f"{rate:.2f}")
            c.drawString(x_positions[7], y, f"{item.total_amount:.2f}")
            c.line(40, y-10, width - 40, y-10)

            total_discount += item.discount * item.quantity
            total_quantity += item.quantity
            total_rate += rate * item.quantity
            total_amount += item.total_amount

            y -= 25
            if y < 100:
                c.showPage()
                y = self.height - 60

        # Subtotal
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x_positions[1], y, "Sub-total Amount")
        c.drawString(x_positions[4], y, f"{total_discount:.2f}")
        c.drawString(x_positions[5], y, f"{total_quantity}")
        c.drawString(x_positions[6], y, f"{total_rate:.2f}")
        c.drawString(x_positions[7], y, f"{total_amount:.2f}")

        return y - 40

    def _draw_commission_deduction(self, c, bill, width, start_y):
        """Draw commission deduction section"""
        y = start_y - 20

        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, f"Commission Deducted for {bill.commission_month}/{bill.commission_year}: ₹{bill.commission_deducted:.2f}")
        y -= 15

        return y

    def _draw_totals(self, c, bill, width, start_y):
        """Draw totals section with left and right columns"""
        y = start_y

        opening_due = bill.op_due_amount or 0
        total_bill = bill.total_amount
        grand_total = total_bill + opening_due # Assuming grand total is the same as total bill for now
        last_paid_balance = bill.last_paid or 0
        due = grand_total - last_paid_balance or 0

        # Left column
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, f"Opening Due         :   {opening_due:.2f}")
        y -= 18
        c.drawString(50, y, f"Bill Amount            :   {bill.total_amount:.2f}")
        y -= 18
        c.drawString(50, y, f"Grand Total           :   {grand_total:.2f}")

        # Right column
        c.drawRightString(width - 60, y + 70, f"Paid Amount :   {last_paid_balance:.2f}")
        if due < 0:
            c.setFillColorRGB(0, 1, 0)  # Green for negative due (wallet amount)
            c.drawRightString(width - 60, y + 50, f"Wallet Amount :   {-due:.2f}")
        else:
            c.setFillColorRGB(1, 0, 0)  # Red for positive due    
            c.drawRightString(width - 60, y + 50, f"Balance Due :   {due:.2f}")

        return y

    def _draw_stamp_and_signature(self, c, width, height):
        """Draw signature only (stamps removed)"""
        footer_y = 60

        # static/images/signature.png
        signature_path = os.path.join(settings.BASE_DIR, "static", "images", "signature.png")

        if os.path.exists(signature_path):
            try:
                signature = ImageReader(signature_path)
                c.saveState()
                c.translate(width - 200, footer_y + 80)
                c.drawImage(signature, 0, 0, width=100, height=100, mask='auto')
                c.restoreState()
            except Exception as e:
                # optional: print(e) or log
                pass

        c.drawRightString(width - 90, footer_y + 70, "AUTHORISED SIGNATURE")


    def _draw_footer(self, c, width, height):
        """Draw footer section"""
        footer_y = 60
        left_margin = 40
        c.setFont("Helvetica", 9)
        text = (
            "Note:\n"
            "- Monthly commission will be settled on the 10th of every month.\n"
            "- Commission applies only to milk and curd packets with an average sale of minimum 25 liters per month.\n"
            "- Goods once sold will not be taken back or exchanged."
        )
        text_lines = text.split('\n')
        y = footer_y + 60
        for line in text_lines:
            c.drawString(left_margin, y, line)
            y -= 15

        # Center-align "Thank you for your business!"
        c.setFont("Helvetica-Bold", 9)
        thank_you_text = "Thank you for your business!"
        text_width = c.stringWidth(thank_you_text, "Helvetica-Bold", 9)
        x_center = (width - text_width) / 2
        c.drawString(x_center, footer_y - 10, thank_you_text)

