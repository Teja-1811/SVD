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

from .models import SaleItem

class PDFGenerator:
    """PDF generation utility for general store sales"""

    def __init__(self):
        self.width, self.height = letter

    def generate_sale_pdf(self, sale):
        """Generate sale PDF and save to file system"""
        sale_items = SaleItem.objects.filter(sale=sale).select_related('product')

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        self._draw_invoice_template(c, sale, sale_items)

        # Save PDF
        pdf = buffer.getvalue()
        pdf_path = f"media/sales/invoices/{sale.invoice_number}.pdf"

        pdf_dir = os.path.dirname(pdf_path)
        os.makedirs(pdf_dir, exist_ok=True)

        with open(pdf_path, 'wb') as f:
            f.write(pdf)

        buffer.close()
        return pdf_path

    def generate_and_return_pdf(self, sale, request=None):
        """Generate PDF and return as HTTP response"""
        sale_items = SaleItem.objects.filter(sale=sale).select_related('product')

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        self._draw_invoice_template(c, sale, sale_items)

        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename=invoice_{sale.invoice_number}.pdf'
        response.write(pdf)

        return response

    def _draw_invoice_template(self, c, sale, sale_items):
        """Draw the complete invoice template"""
        width, height = self.width, self.height

        # Draw border
        margin = 30
        c.setLineWidth(2)
        c.setStrokeColorRGB(0.8, 0, 0)
        c.setTitle(f"Invoice - {sale.invoice_number}")
        c.rect(margin, margin, width - 2*margin, height - 2*margin)

        # Draw company header
        self._draw_company_header(c, width, height)

        # Draw customer details
        y_pos = self._draw_customer_details(c, sale, width, height)

        # Draw items table
        y_pos = self._draw_items_table(c, sale_items, width, y_pos)

        # Draw totals
        y_pos = self._draw_totals(c, sale, width, y_pos)

        # Draw signature
        self._draw_stamp_and_signature(c, width, height)

        # Draw footer
        self._draw_footer(c, width, height)

        c.save()

    def _draw_company_header(self, c, width, height):
        """Draw company header section"""
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, height - 50, "Sri Vijaya Durga General Store")
        c.setFont("Helvetica", 10)
        c.drawString(40, height - 65, "Near Santa Market, Main Road")
        c.drawString(40, height - 80, "Gundugolanu, Bhimadolu, Eluru, AP - 534427")
        c.drawString(40, height - 95, "Phone: 9392890375")

        # Logo
        logo_path = finders.find('images/SVD.png')
        if logo_path and os.path.exists(logo_path):
            try:
                logo = ImageReader(logo_path)
                c.drawImage(logo, 280, height - 110, width=80, height=80, mask='auto')
            except Exception as e:
                pass
        else:
            pass

    def _draw_customer_details(self, c, sale, width, height):
        """Draw customer details section"""
        # Invoice details
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(width - 40, height - 50, f"Invoice No. {sale.invoice_number}")
        c.setFont("Helvetica", 10)
        c.drawRightString(width - 40, height - 65, f"Invoice Date: {sale.invoice_date.strftime('%d %b %Y')}")

        # Customer box
        box_x, box_y = 40, height - 220
        box_width, box_height = width - 80, 100

        c.setStrokeColorRGB(0.8, 0, 0)
        c.setLineWidth(1)
        c.roundRect(box_x, box_y, box_width, box_height, 10, stroke=1, fill=0)

        c.setFont("Helvetica-Bold", 12)
        c.drawString(box_x + 10, box_y + box_height - 20, "Bill To")
        c.setFont("Helvetica-Bold", 10)
        c.drawString(box_x + 10, box_y + box_height - 40, sale.customer.name)
        c.setFont("Helvetica", 10)
        if sale.customer.phone:
            c.drawString(box_x + 10, box_y + box_height - 55, f"Phone: {sale.customer.phone}")
        if sale.customer.address:
            c.drawString(box_x + 10, box_y + box_height - 70, f"Address: {sale.customer.address}")

        return box_y - 20

    def _draw_items_table(self, c, sale_items, width, start_y):
        """Draw items table with calculations"""
        y = start_y

        # Headers
        c.setFont("Helvetica-Bold", 10)
        headers = ["#", "Product Details", "MRP", "Price/Unit", "Disc./Unit", "Qty", "Rate", "Total"]
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

        for idx, item in enumerate(sale_items, start=1):
            rate = item.price_per_unit - item.discount
            c.drawString(x_positions[0], y, f"{idx:02d}")
            c.drawString(x_positions[1], y, item.product.name)
            c.drawString(x_positions[2], y, f"{item.product.mrp:.2f}")
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

    def _draw_totals(self, c, sale, width, start_y):
        """Draw totals section"""
        y = start_y

        total_amount = sale.total_amount
        due_amount = sale.due_amount
        last_paid = sale.last_paid or 0

        # Left column
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, f"Total Amount         :   ₹{total_amount:.2f}")
        y -= 18
        c.drawString(50, y, f"Due Amount           :   ₹{due_amount:.2f}")
        y -= 18
        c.drawString(50, y, f"Last Paid            :   ₹{last_paid:.2f}")

        # Amount in words
        try:
            amount_in_words = num2words(int(total_amount), lang='en_IN').title()
            c.setFont("Helvetica", 10)
            c.drawString(50, y - 25, f"Amount in Words: {amount_in_words} Rupees Only")
        except:
            pass

        return y - 60

    def _draw_stamp_and_signature(self, c, width, height):
        """Draw signature"""
        footer_y = 60

        signature_path = finders.find('images/N. Ramesh.png')

        if signature_path and os.path.exists(signature_path):
            try:
                signature = ImageReader(signature_path)
                c.saveState()
                c.translate(width - 200, footer_y + 80)
                c.drawImage(signature, 0, 0, width=100, height=100, mask='auto')
                c.restoreState()
            except Exception as e:
                pass
        else:
            pass

        c.drawRightString(width - 90, footer_y + 70, "AUTHORISED SIGNATURE")

    def _draw_footer(self, c, width, height):
        """Draw footer section"""
        footer_y = 60
        left_margin = 40
        c.setFont("Helvetica", 9)
        text = (
            "Note:\n"
            "- Goods once sold will not be taken back or exchanged.\n"
            "- All disputes are subject to Gundugolanu jurisdiction only."
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
