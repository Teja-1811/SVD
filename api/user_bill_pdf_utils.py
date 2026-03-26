import os
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.http import HttpResponse
from num2words import num2words
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from milk_agency.models import BillItem
from milk_agency.order_pricing import DELIVERY_ITEM_CODE
from milk_agency.utils import InvoicePDFUtils

from .user_api_helpers import find_linked_order_for_bill, get_delivery_charge_for_bill


class UserPDFGenerator:
    """User invoice PDF generator aligned with the admin invoice layout."""

    def __init__(self):
        self.width, self.height = landscape(letter)
        self.margin = 20

    def generate_invoice_pdf(self, bill):
        bill_items = list(BillItem.objects.filter(bill=bill).select_related("item"))
        display_items = [item for item in bill_items if getattr(item.item, "code", "") != DELIVERY_ITEM_CODE]

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=landscape(letter))
        self._draw_invoice_template(c, bill, bill_items, display_items)

        pdf = buffer.getvalue()
        pdf_path = InvoicePDFUtils.get_invoice_pdf_path(bill.invoice_number)
        pdf_dir = os.path.dirname(pdf_path)
        os.makedirs(pdf_dir, exist_ok=True)

        with open(pdf_path, "wb") as pdf_file:
            pdf_file.write(pdf)

        buffer.close()
        return pdf_path

    def generate_and_return_pdf(self, bill, request=None):
        bill_items = list(BillItem.objects.filter(bill=bill).select_related("item"))
        display_items = [item for item in bill_items if getattr(item.item, "code", "") != DELIVERY_ITEM_CODE]

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=landscape(letter))
        self._draw_invoice_template(c, bill, bill_items, display_items)

        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename=user_invoice_{bill.invoice_number}.pdf"
        response.write(pdf)
        return response

    def _money(self, value):
        return f"{Decimal(value or 0):.2f}"

    def _safe(self, value):
        return str(value or "").strip()

    def _draw_invoice_template(self, c, bill, bill_items, display_items):
        c.setTitle(f"Invoice - {bill.invoice_number}")
        c.setLineWidth(1)

        x0 = self.margin
        y0 = self.margin
        w = self.width - (2 * self.margin)
        h = self.height - (2 * self.margin)

        c.rect(x0, y0, w, h)

        y = self.height - self.margin
        y = self._draw_top_header(c, x0, y, w)
        y = self._draw_bill_heading(c, x0, y, w)
        y = self._draw_invoice_meta(c, bill, x0, y, w)
        y = self._draw_party_section(c, bill, x0, y, w)
        y, totals = self._draw_items_table(c, display_items, x0, y, w)
        self._draw_footer_sections(c, bill, bill_items, x0, y, w, totals)

        c.save()

    def _draw_top_header(self, c, x, y_top, w):
        row_h = 74
        y = y_top - row_h
        c.rect(x, y, w, row_h)

        logo_path = os.path.join(settings.BASE_DIR, "static", "images", "logo.webp")
        if os.path.exists(logo_path):
            try:
                logo = ImageReader(logo_path)
                c.drawImage(logo, x + 8, y + 14, width=110, height=44, mask="auto")
            except Exception:
                pass

        center_x = x + (w / 2)

        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(center_x, y + 56, "DODLA DAIRY LIMITED")

        c.setFont("Helvetica", 7)
        c.drawCentredString(center_x, y + 44, "FSSAI No: 10012044000145, PAN No: AABCD5077E, CIN No: L15209TG1995PLC020324")
        c.drawCentredString(center_x, y + 34, "GSTIN: 37AACCD5077E1ZQ")
        c.drawCentredString(center_x, y + 24, "Dhulipalli Village, Guntur, Guntur, 522403, Andhra Pradesh, India")

        return y

    def _draw_bill_heading(self, c, x, y_top, w):
        row_h = 34
        y = y_top - row_h
        c.rect(x, y, w, row_h)

        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x + (w / 2), y + 21, "Bill of Supply")
        c.setFont("Helvetica", 9)
        c.drawCentredString(x + (w / 2), y + 8, "(Original/Duplicate/Triplicate)")

        return y

    def _draw_invoice_meta(self, c, bill, x, y_top, w):
        row_h = 34
        y = y_top - row_h
        c.rect(x, y, w, row_h)

        c.setFont("Helvetica", 8.5)
        c.drawString(x + 8, y + 18, f"Invoice No: {self._safe(bill.invoice_number)}")
        c.drawString(x + 220, y + 18, f"Invoice Date: {bill.invoice_date.strftime('%Y-%m-%d')}")

        order_date, delivery_date = self._get_order_dates(bill)
        if order_date:
            c.drawString(x + 420, y + 18, f"Order Date: {order_date.strftime('%Y-%m-%d')}")
        if delivery_date:
            c.drawCentredString(x + (w / 2), y + 7, f"Delivery: {delivery_date.strftime('%Y-%m-%d')}")

        return y

    def _draw_party_section(self, c, bill, x, y_top, w):
        row_h = 92
        y = y_top - row_h
        c.rect(x, y, w, row_h)

        mid_x = x + (w * 0.52)
        c.line(mid_x, y, mid_x, y + row_h)

        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 8, y + row_h - 14, "Ship From")
        c.drawString(mid_x + 8, y + row_h - 14, "Bill/Ship To")

        c.setFont("Helvetica", 8)
        c.drawString(x + 8, y + row_h - 28, "Sri Vijaya Durga Milk Agencies")
        c.drawString(x + 8, y + row_h - 40, "Near Santa Market, Main Road")
        c.drawString(x + 8, y + row_h - 52, "Gundugolanu, Bhimadolu, Eluru, AP - 534427")
        c.drawString(x + 8, y + row_h - 64, "Phone: 9392890375")

        customer = bill.customer
        cust_name = self._safe(getattr(customer, "name", ""))
        shop_name = self._safe(getattr(customer, "shop_name", ""))
        phone = self._safe(getattr(customer, "phone", ""))

        address_parts = [
            self._safe(getattr(customer, "flat_number", "")),
            self._safe(getattr(customer, "area", "")),
            self._safe(getattr(customer, "city", "")),
            self._safe(getattr(customer, "state", "")),
            self._safe(getattr(customer, "pin_code", "")),
        ]
        address = ", ".join([part for part in address_parts if part])

        c.drawString(mid_x + 8, y + row_h - 28, cust_name)
        if shop_name:
            c.drawString(mid_x + 8, y + row_h - 40, f"Shop: {shop_name}")
        c.drawString(mid_x + 8, y + row_h - 52, address)
        c.drawString(mid_x + 8, y + row_h - 64, f"Phone: {phone}")

        return y

    def _draw_items_table(self, c, bill_items, x, y_top, w):
        table_h = 245
        y = y_top - table_h
        c.rect(x, y, w, table_h)

        headers = ["#", "Item Code", "Product Description", "MRP", "Rate", "Disc", "Qty", "Amount"]
        col_widths = [24, 66, 294, 58, 58, 58, 52, 82]
        header_h = 24

        x_cursor = x
        for col_w in col_widths[:-1]:
            x_cursor += col_w
            c.line(x_cursor, y, x_cursor, y + table_h)

        c.line(x, y + table_h - header_h, x + w, y + table_h - header_h)

        c.setFont("Helvetica-Bold", 8)
        hx = x
        for idx, header in enumerate(headers):
            c.drawString(hx + 4, y + table_h - 16, header)
            hx += col_widths[idx]

        total_discount = Decimal("0")
        total_qty = 0
        total_amount = Decimal("0")

        row_h = 18
        max_rows = int((table_h - header_h - 24) / row_h)
        rows = list(bill_items[:max_rows])

        c.setFont("Helvetica", 8)
        for i, bill_item in enumerate(rows, start=1):
            row_y_top = y + table_h - header_h - ((i - 1) * row_h)
            row_y_text = row_y_top - 13
            c.line(x, row_y_top - row_h, x + w, row_y_top - row_h)

            code = self._safe(getattr(bill_item.item, "code", ""))
            name = self._safe(getattr(bill_item.item, "name", ""))
            mrp = Decimal(getattr(bill_item.item, "mrp", 0) or 0)
            rate = Decimal(bill_item.price_per_unit or 0)
            disc = Decimal(bill_item.discount or 0)
            qty = int(bill_item.quantity or 0)
            amount = Decimal(bill_item.total_amount or 0)

            total_discount += disc * qty
            total_qty += qty
            total_amount += amount

            row_values = [
                str(i),
                code,
                name[:58],
                f"{mrp:.2f}",
                f"{rate:.2f}",
                f"{disc:.2f}",
                str(qty),
                f"{amount:.2f}",
            ]

            vx = x
            for col_i, value in enumerate(row_values):
                c.drawString(vx + 4, row_y_text, value)
                vx += col_widths[col_i]

        subtotal_y = y + 6
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x + col_widths[0] + col_widths[1] + 4, subtotal_y + 4, "Totals")
        c.drawString(x + sum(col_widths[:5]) + 4, subtotal_y + 4, f"{total_discount:.2f}")
        c.drawString(x + sum(col_widths[:6]) + 4, subtotal_y + 4, str(total_qty))
        c.drawString(x + sum(col_widths[:7]) + 4, subtotal_y + 4, f"{total_amount:.2f}")

        return y, {
            "total_discount": total_discount,
            "total_qty": total_qty,
            "total_amount": total_amount,
        }

    def _draw_footer_sections(self, c, bill, bill_items, x, y_top, w, totals):
        footer_h = y_top - self.margin
        y = self.margin
        c.rect(x, y, w, footer_h)

        left_w = w * 0.65
        c.line(x + left_w, y, x + left_w, y + footer_h)

        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + 8, y + footer_h - 16, "Payment Details")
        c.setFont("Helvetica", 8)
        c.drawString(x + 8, y + footer_h - 28, "Mode: Cash / UPI")

        opening_due = Decimal(bill.op_due_amount or 0)
        delivery_charge = self._get_delivery_charge(bill, bill_items)
        bill_amount = Decimal(bill.total_amount or 0) - delivery_charge
        grand_total = opening_due + bill_amount + delivery_charge
        paid_amount = Decimal(bill.last_paid or 0)
        due_amount = grand_total - paid_amount

        in_words = num2words(grand_total, to="cardinal", lang="en_IN")
        c.drawString(x + 8, y + footer_h - 44, f"Amount in words: {in_words.title()} only")

        c.setFont("Helvetica", 7.5)
        c.drawString(x + 8, y + 44, "Declaration:")
        c.drawString(x + 8, y + 32, "Goods once sold will not be taken back or exchanged.")
        c.drawString(x + 8, y + 20, "This is a computer generated invoice; signature not required.")

        summary_x = x + left_w + 8
        base_y = y + footer_h - 18

        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(summary_x, base_y, "Summary")

        c.setFont("Helvetica", 8)
        c.drawString(summary_x, base_y - 14, f"Opening Due   : {self._money(opening_due)}")
        c.drawString(summary_x, base_y - 26, f"Bill Amount   : {self._money(bill_amount)}")
        c.drawString(summary_x, base_y - 38, f"Delivery Chg  : {self._money(delivery_charge)}")
        c.drawString(summary_x, base_y - 50, f"Grand Total   : {self._money(grand_total)}")
        c.drawString(summary_x, base_y - 62, f"Paid Amount   : {self._money(paid_amount)}")

        if due_amount >= 0:
            c.drawString(summary_x, base_y - 74, f"Balance Due   : {self._money(due_amount)}")
        else:
            c.drawString(summary_x, base_y - 74, f"Wallet Amount : {self._money(-due_amount)}")

        signature_path = os.path.join(settings.BASE_DIR, "static", "images", "signature.png")
        if os.path.exists(signature_path):
            try:
                signature = ImageReader(signature_path)
                c.drawImage(signature, x + w - 130, y + 26, width=90, height=46, mask="auto")
            except Exception:
                pass

        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(x + w - 20, y + 18, "AUTHORISED SIGNATORY")

    def _get_related_order(self, bill):
        return find_linked_order_for_bill(getattr(bill, "customer", None), bill)

    def _get_order_dates(self, bill):
        order = self._get_related_order(bill)
        if not order:
            return None, None
        return order.order_date, order.delivery_date

    def _get_delivery_charge(self, bill, bill_items):
        return get_delivery_charge_for_bill(
            bill,
            bill_items=bill_items,
            linked_order=self._get_related_order(bill),
        )
