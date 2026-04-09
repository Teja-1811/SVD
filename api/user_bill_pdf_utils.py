import os
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.http import HttpResponse
from django.contrib.staticfiles import finders
from num2words import num2words
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from milk_agency.order_pricing import DELIVERY_ITEM_CODE
from milk_agency.utils import InvoicePDFUtils

from .user_api_helpers import find_linked_order_for_bill, get_delivery_charge_for_bill


class UserPDFGenerator:
    """User invoice PDF generator aligned with the admin invoice layout."""

    def __init__(self):
        self.width, self.height = landscape(letter)
        self.margin = 20

    def generate_invoice_pdf(self, bill):
        bill_items = list(bill.items.all().select_related("item"))
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
        bill_items = list(bill.items.all().select_related("item"))
        display_items = [item for item in bill_items if getattr(item.item, "code", "") != DELIVERY_ITEM_CODE]

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=landscape(letter))
        self._draw_invoice_template(c, bill, bill_items, display_items)

        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{bill.invoice_number}.pdf"'
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
        self._draw_terms_page(c)

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

        header_logo_path = self._resolve_static_image("images/SVD1.png")
        if header_logo_path:
            try:
                header_logo = ImageReader(header_logo_path)
                logo_width = 64
                logo_height = 64
                logo_x = x + w - logo_width - 16
                logo_y = y + (row_h - logo_height) / 2
                c.drawImage(header_logo, logo_x, logo_y, width=logo_width, height=logo_height, mask="auto")
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

    def _resolve_static_image(self, *relative_paths):
        """Resolve a static image path for ReportLab image loading."""
        for rel_path in relative_paths:
            finder_path = finders.find(rel_path)
            if finder_path:
                return finder_path

            candidate_paths = [
                os.path.join(settings.BASE_DIR, "static", rel_path),
                os.path.join(settings.BASE_DIR, "staticfiles", rel_path),
            ]
            for path in candidate_paths:
                if os.path.exists(path):
                    return path
        return None

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
        c.drawString(x + 8, y + row_h - 40, "Main road Gundugolanu, Near Santa Market")
        c.drawString(x + 8, y + row_h - 52, "Besides Srivasa Pesticides, Gundugolanu, Bhimadolu Mandal")
        c.drawString(x + 8, y + row_h - 64, "Eluru Dist - 534427")
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
        c.drawString(x + 8, y + footer_h - 28, "Mode: Cash / Paytm / Bank Transfer")

        opening_due = Decimal(bill.op_due_amount or 0)
        delivery_charge = self._get_delivery_charge(bill, bill_items)
        bill_amount = Decimal(bill.total_amount or 0) - delivery_charge
        grand_total = opening_due + bill_amount + delivery_charge
        paid_amount = Decimal(bill.last_paid or 0)
        due_amount = grand_total - paid_amount

        in_words = num2words(grand_total, to="cardinal", lang="en_IN")
        c.drawString(x + 8, y + footer_h - 44, f"Amount in words: {in_words.title()} only")

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

    def _draw_wrapped_text(self, c, text, x, y, max_width, font_name="Helvetica", font_size=8, leading=10):
        """Draw wrapped footer text without overflowing the page width."""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            if c.stringWidth(test_line, font_name, font_size) <= max_width or not current_line:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        c.setFont(font_name, font_size)
        text_y = y
        for line in lines:
            c.drawString(x, text_y, line)
            text_y -= leading
        return text_y

    def _draw_terms_page(self, c):
        c.showPage()
        c.setLineWidth(1)

        x0 = self.margin
        y0 = self.margin
        w = self.width - (2 * self.margin)
        h = self.height - (2 * self.margin)
        c.rect(x0, y0, w, h)

        y = self.height - self.margin
        y = self._draw_top_header(c, x0, y, w)

        title_h = 36
        title_y = y - title_h
        c.rect(x0, title_y, w, title_h)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x0 + (w / 2), title_y + 22, "Terms, Conditions & Disclaimer")
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(x0 + (w / 2), title_y + 10, "Please review the billing terms below carefully.")

        content_top = title_y - 16
        left_x = x0 + 20
        right_x = x0 + (w * 0.62)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(left_x, content_top, "Terms & Conditions")
        terms = [
            "1. Goods once sold will not be taken back or exchanged.",
            "2. Please verify the delivered quantities and bill amount at the time of receipt.",
            "3. This is a computer generated invoice; signature on the invoice page is not mandatory.",
            "4. Payments should be settled only with Sri Vijaya Durga Milk Agencies against valid billing records.",
        ]
        term_y = content_top - 18
        for term in terms:
            term_y = self._draw_wrapped_text(c, term, left_x, term_y, right_x - left_x - 20, font_size=8.5, leading=12)
            term_y -= 6

        c.setFont("Helvetica-Bold", 10)
        disclaimer_title_y = term_y - 8
        c.drawString(left_x, disclaimer_title_y, "Disclaimer")
        disclaimer = (
            "Partnering companies are not responsible for this bill. Sri Vijaya Durga Milk Agencies is solely "
            "accountable for this bill. For any bill-related issue, please contact only SVD Agencies. Partner "
            "company details are shown only for trust-building and marketing purposes."
        )
        self._draw_wrapped_text(c, disclaimer, left_x, disclaimer_title_y - 18, right_x - left_x - 20, font_size=8.5, leading=12)

        c.setLineWidth(1)
        c.line(right_x - 12, y0 + 24, right_x - 12, title_y - 10)

        sign_top = title_y - 6
        c.setFont("Helvetica-Bold", 10)
        c.drawString(right_x + 12, sign_top - 16, "Accountability")
        accountability = (
            "Sri Vijaya Durga Milk Agencies is the only accountable billing party for this invoice."
        )
        text_bottom = self._draw_wrapped_text(c, accountability, right_x + 12, sign_top - 34, x0 + w - right_x - 28, font_size=8.5, leading=12)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(right_x + 12, text_bottom - 12, "Contact")
        contact_lines = [
            "Sri Vijaya Durga Milk Agencies",
            "Main road Gundugolanu, Near Santa Market",
            "Besides Srivasa Pesticides, Gundugolanu, Bhimadolu Mandal",
            "Eluru Dist - 534427",
            "Phone: 9392890375",
        ]
        contact_y = text_bottom - 30
        c.setFont("Helvetica", 8.5)
        for line in contact_lines:
            c.drawString(right_x + 12, contact_y, line)
            contact_y -= 12

        signature_path = os.path.join(settings.BASE_DIR, "static", "images", "signature.png")
        if os.path.exists(signature_path):
            try:
                signature = ImageReader(signature_path)
                c.drawImage(signature, x0 + w - 150, y0 + 90, width=100, height=52, mask="auto")
            except Exception:
                pass

        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(x0 + w - 24, y0 + 78, "AUTHORISED SIGNATORY")
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x0 + (w / 2), y0 + 22, "Thank you for your business!")
