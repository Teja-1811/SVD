import os
from django.core.management.base import BaseCommand
from django.db import transaction
from milk_agency.models import Bill
from milk_agency.pdf_utils import PDFGenerator
from milk_agency.utils import InvoicePDFUtils

class Command(BaseCommand):
    help = 'Generate invoice PDFs for all bills in the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be generated without actually creating PDFs.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate PDFs even if they already exist.',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm generation of PDFs for all bills.',
        )

    def handle(self, *args, **kwargs):
        dry_run = kwargs['dry_run']
        force = kwargs['force']
        confirm = kwargs['confirm']

        # Get all bills
        bills = Bill.objects.all().order_by('id')
        total_bills = bills.count()

        if total_bills == 0:
            self.stdout.write(self.style.WARNING('No bills found in the database.'))
            return

        # Count bills that need PDF generation
        bills_to_process = []
        for bill in bills:
            pdf_path = InvoicePDFUtils.get_invoice_pdf_path(bill.invoice_number)
            if force or not os.path.exists(pdf_path):
                bills_to_process.append(bill)

        process_count = len(bills_to_process)

        if process_count == 0:
            self.stdout.write(self.style.SUCCESS('All bills already have PDFs. Use --force to regenerate.'))
            return

        # Show summary
        self.stdout.write(f'Found {total_bills} bills in the database.')
        self.stdout.write(f'{process_count} bills need PDF generation.')
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.SUCCESS('DRY RUN - No PDFs were actually generated.'))
            for bill in bills_to_process[:5]:  # Show first 5
                self.stdout.write(f'  Would generate PDF for bill {bill.id}: {bill.invoice_number}')
            if process_count > 5:
                self.stdout.write(f'  ... and {process_count - 5} more')
            return

        if not confirm:
            self.stdout.write(self.style.ERROR('Generation cancelled. Use --confirm flag to proceed.'))
            return

        # Proceed with generation
        self.stdout.write('Starting PDF generation process...')

        pdf_generator = PDFGenerator()
        success_count = 0
        error_count = 0

        for i, bill in enumerate(bills_to_process, 1):
            try:
                self.stdout.write(f'Processing bill {i}/{process_count}: {bill.invoice_number} (ID: {bill.id})')

                # Generate PDF
                pdf_path = pdf_generator.generate_invoice_pdf(bill)

                if os.path.exists(pdf_path):
                    # Update bill.pdf_file field with relative path to MEDIA_ROOT
                    from django.conf import settings
                    relative_path = os.path.relpath(pdf_path, settings.MEDIA_ROOT)
                    bill.pdf_file.name = relative_path.replace("\\", "/")  # Normalize for Django FileField
                    bill.save()
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✅ Generated PDF: {pdf_path}'))
                else:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f'  ❌ PDF file not found after generation: {pdf_path}'))

            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f'  ❌ Error generating PDF for bill {bill.id}: {str(e)}'))

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('PDF generation completed!'))
        self.stdout.write('Summary:')
        self.stdout.write(f'  • Total bills processed: {process_count}')
        self.stdout.write(f'  • Successful: {success_count}')
        self.stdout.write(f'  • Errors: {error_count}')
        if error_count > 0:
            self.stdout.write(self.style.WARNING('Some PDFs failed to generate. Check the errors above.'))
