import os
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from reportlab.lib.pagesizes import letter, landscape, A3
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer, PageTemplate, Frame, BaseDocTemplate
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from django.contrib.staticfiles import finders
from django.http import HttpResponse

class MonthlySalesPDFGenerator:
    """PDF generation utility for monthly sales summary"""

    def __init__(self):
        self.width, self.height = landscape(A3)
        self.margin_bottom = 100  # Minimum space needed at bottom for footer

    def generate_monthly_sales_pdf(self, context, request=None):
        """Generate monthly sales summary PDF and return as HTTP response"""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=landscape(A3))
        customer = context['selected_customer_obj']
        self._draw_monthly_sales_template(c, context)

        c.setTitle(f"{customer.name} Monthly Sales - {context['selected_date'].strftime('%B %Y')}")
        c.save()

        pdf = buffer.getvalue()
        buffer.close()

        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{customer.name}_{context["selected_date"].strftime("%B_%Y")}.pdf"'
        response.write(pdf)

        return response

    def _draw_monthly_sales_template(self, c, context):
        """Draw the complete monthly sales summary template with page breaks when content overlaps"""
        width, height = self.width, self.height

        # Draw border
        margin = 30
        c.setLineWidth(2)
        c.setStrokeColorRGB(0.8, 0, 0)
        c.rect(margin, margin, width - 2*margin, height - 2*margin)

        # Draw watermark
        self._draw_watermark(c, width, height)

        # Draw company header
        y_pos = self._draw_company_header(c, context, width, height)

        # Draw purchase details table
        y_pos = self._draw_purchase_details_table(c, context, width, y_pos)

        # Check if commission details fit on current page
        if y_pos - 200 < self.margin_bottom:  # Estimate space needed for commission details
            c.showPage()
            # Redraw border on new page
            c.setLineWidth(2)
            c.setStrokeColorRGB(0.8, 0, 0)
            c.rect(margin, margin, width - 2*margin, height - 2*margin)
            # Redraw watermark on new page
            self._draw_watermark(c, width, height)
            y_pos = height - 50  # Reset y_pos for new page

        # Draw commission details
        y_pos = self._draw_commission_details(c, context, width, y_pos)

        # Check if final summary fits on current page
        if y_pos - 100 < self.margin_bottom:  # Estimate space needed for final summary
            c.showPage()
            # Redraw border on new page
            c.setLineWidth(2)
            c.setStrokeColorRGB(0.8, 0, 0)
            c.rect(margin, margin, width - 2*margin, height - 2*margin)
            # Redraw watermark on new page
            self._draw_watermark(c, width, height)
            y_pos = height - 50  # Reset y_pos for new page

        # Draw final summary
        y_pos = self._draw_final_summary(c, context, width, y_pos)

        # Check if signature and footer fit on current page
        if y_pos - 150 < self.margin_bottom:  # Estimate space needed for signature and footer
            c.showPage()
            # Redraw border on new page
            c.setLineWidth(2)
            c.setStrokeColorRGB(0.8, 0, 0)
            c.rect(margin, margin, width - 2*margin, height - 2*margin)
            # Redraw watermark on new page
            self._draw_watermark(c, width, height)

        # Draw signature
        self._draw_signature(c, width, height)

        # Draw footer
        self._draw_footer(c, width, height)



    def _draw_company_header(self, c, context, width, height):
        """Draw company header section with left-center-right layout"""
        c.setFont("Helvetica-Bold", 12)

        # Left section - Company details
        left_x = 40
        c.drawString(left_x, height - 50, "Sri Vijaya Durga Milk Agencies")
        c.setFont("Helvetica", 12)
        c.drawString(left_x, height - 65, "D.No: 10-92, Gundugolanu, Bhimadolu,Eluru, Andhra Pradesh - 534427")
        c.drawString(left_x, height - 80, "Email: svdagencies12@gmail")
        c.drawString(left_x, height - 95, "Phone: 9392890375")

        # Center section - Logo
        logo_path = finders.find('images/SVD1.png')
        if logo_path and os.path.exists(logo_path):
            try:
                logo = ImageReader(logo_path)
                logo_width = 100
                logo_height = 100
                logo_x = (width - logo_width) / 2  # Center horizontally
                c.drawImage(logo, logo_x, height - 135, width=logo_width, height=logo_height, mask='auto')
            except Exception as e:
                pass

        # Right section - Customer details next to logo
        customer = context['selected_customer_obj']
        right_x = logo_x + logo_width + 100  # Position next to logo
        c.setFont("Helvetica-Bold", 12)
        c.drawString(right_x, height - 50, f"{customer.name} - {customer.shop_name}")
        c.setFont("Helvetica", 12)
        c.drawString(right_x, height - 65, f"Retailer ID: {customer.retailer_id or 'N/A'}")
        if customer.city == "DDL":
            city_display = "Denduluru"
        else:
            city_display = "Bhimadolu"
        address = f"{customer.flat_number or ''}, {customer.area or ''}, { city_display } (M), Eluru Dist, {customer.state or ''} - {customer.pin_code or ''}"
        c.drawString(right_x, height - 80, f"Address: {address}")
        c.drawString(right_x, height - 95, f"Phone: {customer.phone or 'N/A'}")

        # Title below header with lines above and below
        c.setFont("Helvetica-Bold", 10)
        title_text = f"Customer Statement for the Period: {context['start_date'].strftime('%d %b %Y')} - {context['end_date'].strftime('%d %b %Y')}"
        text_width = c.stringWidth(title_text, "Helvetica-Bold", 10)
        x_center = (width - text_width) / 2
        y_title = height - 150

        # Draw line above title (red, full width)
        c.setStrokeColorRGB(1, 0, 0)  # Red color
        c.setLineWidth(1.2)
        c.line(40, y_title + 12, width - 40, y_title + 12)

        # Draw title (red)
        c.setFillColorRGB(0, 0, 0)  # Red color
        c.drawString(x_center, y_title - 3, title_text)
        c.setFillColorRGB(0, 0, 0)  # Reset to black

        # Draw line below title (red, full width)
        c.line(40, y_title-10, width - 40, y_title-10)

        return y_title - 20  # Return the y position after the header



    def _draw_purchase_details_table(self, c, context, width, start_y):
        """Draw purchase details table using Table class"""
        y = start_y - 10
        y -= 20

        # Prepare table data
        headers = ["Date"] + list(context['unique_codes']) + ["Invoice", "Paid", "Due"]
        data = [headers]

        for date_obj in context['date_range']:
            date_key = date_obj.strftime('%Y-%m-%d')
            if date_key in context['customer_bills']:
                bill = context['customer_bills'][date_key]
                row = [date_obj.strftime('%d-%m-%Y')]
                for item_code in context['unique_codes']:
                    qty = context['customer_items_data'].get(item_code, {}).get(date_key, 0)
                    row.append(str(qty))
                row.extend([f"{bill['total_amount']:.2f}", f"{bill['paid_amount']:.2f}", f"{bill['due_amount']:.2f}"])
                data.append(row)

        # Totals row
        totals_row = ["Total"]
        for item_code in context['unique_codes']:
            total = context['total_quantity_per_item'].get(item_code, 0)
            totals_row.append(str(total))
        totals_row.extend([f"{context['total_sales']:.2f}", f"{context['paid_amount']:.2f}", f"{context['due_amount']:.2f}"])
        data.append(totals_row)

        # Create table with auto-stretching columns
        num_cols = len(headers)
        available_width = width - 80  # Margin on both sides
        col_width = available_width / num_cols
        table = Table(data, colWidths=[col_width] * num_cols)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))

        # Draw table centered
        table.wrapOn(c, width, self.height)
        table_x = (width - table._width) / 2
        table.drawOn(c, table_x, y - table._height)

        return y - table._height - 40

    def _draw_commission_details(self, c, context, width, start_y):
        """Draw commission details using Table class"""
        if context['avg_volume'] <= 25:
            # Display average volume instead of commission details
            c.setFont("Helvetica-Bold", 10)
            c.drawString(40, start_y, f"Average Sale Of this Month: {context['avg_volume']:.2f} Liters")
            return start_y - 20  # Return adjusted y position

        y = start_y

        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, "Commission Details")
        y -= 10

        # Prepare table data
        headers = [f"Total AVG Sale - {context['avg_volume']:.2f}", "Milk", "Curd", "Total Commission (RS)"]
        data = [headers]

        # Volume row
        volume_row = ["Volume (Liters)", f"{context['milk_volume']:.2f}", f"{context['curd_volume']:.2f}", f"{context['total_commission']:.2f}"]
        data.append(volume_row)

        # Commission Rate row
        rate_row = ["Commission Rate (RS/Liter)", f"{context['milk_commission_rate']:.2f}", f"{context['curd_commission_rate']:.2f}", ""]
        data.append(rate_row)

        # Base Commission Amount row
        base_row = ["Base Commission Amount (RS)", f"{context['milk_volume']*context['milk_commission_rate']:.2f}", f"{context['curd_volume']*context['curd_commission_rate']:.2f}", ""]
        data.append(base_row)

        # Additional Commission if applicable
        if context['avg_volume'] > 35:
            additional_row = ["Additional Commission (RS/Liter above 35)", f"{(context['avg_volume']-35):.2f}", "", ""]
            data.append(additional_row)

        # Create table with auto-stretching columns
        num_cols = len(headers)
        available_width = width - 80  # Margin on both sides
        col_width = available_width / num_cols
        table = Table(data, colWidths=[col_width] * num_cols)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10)
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        # Draw table centered
        table.wrapOn(c, width, self.height)
        table_x = (width - table._width) / 2
        table.drawOn(c, table_x, y - table._height)

        return y - table._height - 20

    def _draw_final_summary(self, c, context, width, start_y):
        """Draw final summary"""
        bottom_y = start_y - 100

        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, bottom_y + 50, "Final Summary")

        c.setFont("Helvetica", 10)
        c.drawString(40, bottom_y + 30, f"Due: {context['due_amount']:.2f}")
        c.drawString(40, bottom_y + 15, f"Commission: {context['total_commission']:.2f}")
        c.drawString(40, bottom_y, f"Remaining Due: {context['remaining_due']:.2f}")

        return 260  # Return value to prevent unnecessary page break

    def _draw_watermark(self, c, width, height):
        """Draw logo as watermark on the page"""
        logo_path = finders.find('images/SVD1.png')
        if logo_path and os.path.exists(logo_path):
            try:
                logo = ImageReader(logo_path)
                c.saveState()
                c.setFillAlpha(0.1)  # Set transparency for watermark
                logo_width = 300
                logo_height = 300
                logo_x = (width - logo_width) / 2
                logo_y = (height - logo_height) / 2
                c.drawImage(logo, logo_x, logo_y, width=logo_width, height=logo_height, mask='auto')
                c.restoreState()
            except Exception as e:
                pass

    def _draw_signature(self, c, width, height):
        """Draw signature"""
        footer_y = 60

        signature_path = finders.find('images/N. Ramesh.png')
        if signature_path and os.path.exists(signature_path):
            try:
                signature = ImageReader(signature_path)
                c.saveState()
                c.translate(width - 200, footer_y + 120)
                c.drawImage(signature, 0, 0, width=100, height=100, mask='auto')
                c.restoreState()
            except Exception as e:
                pass

        c.drawRightString(width - 90, footer_y + 110, "AUTHORISED SIGNATORY")

    def _draw_footer(self, c, width, height):
        """Draw footer section"""
        footer_y = 60
        left_margin = 40
        c.setFont("Helvetica", 10)
        text = (
            "Note:\n"
            "- Monthly commission will be settled by the 10th of every month.\n"
            "- Commission applies only to milk and curd packets with an average sale of minimum 25 liters per month.\n"
            "- Goods once sold will not be taken back or exchanged."
        )
        text_lines = text.split('\n')
        y = footer_y + 120
        for line in text_lines:
            c.drawString(left_margin, y, line)
            y -= 15

        # Center-align "Thank you for your business!"
        c.setFont("Helvetica-Bold", 12)
        thank_you_text = "Thank you for your business!"
        text_width = c.stringWidth(thank_you_text, "Helvetica-Bold", 9)
        x_center = (width - text_width) / 2
        c.drawString(x_center, footer_y - 10, thank_you_text)
