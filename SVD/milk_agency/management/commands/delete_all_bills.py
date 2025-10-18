import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from milk_agency.models import Bill, BillItem, Customer

class Command(BaseCommand):
    help = 'Deletes ALL bills and their associated data. Use with extreme caution!'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm that you want to delete ALL bills. This action cannot be undone.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting anything.',
        )

    def handle(self, *args, **kwargs):
        confirm = kwargs['confirm']
        dry_run = kwargs['dry_run']

        # Get all bills
        bills = Bill.objects.all()
        bill_count = bills.count()

        if bill_count == 0:
            self.stdout.write(self.style.WARNING('No bills found in the database.'))
            return

        # Get all bill items
        bill_items = BillItem.objects.filter(bill__in=bills)
        bill_items_count = bill_items.count()

        # Calculate total customers affected
        affected_customers = bills.values_list('customer', flat=True).distinct().count()

        # Show what will be deleted
        self.stdout.write(self.style.WARNING('⚠️  WARNING: This will permanently delete ALL bills!'))
        self.stdout.write('')
        self.stdout.write('The following data will be deleted:')
        self.stdout.write(f'  • {bill_count} bills')
        self.stdout.write(f'  • {bill_items_count} bill items')
        self.stdout.write(f'  • {affected_customers} customers will have their due amounts reset')
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.SUCCESS('DRY RUN - No data was actually deleted.'))
            return

        if not confirm:
            self.stdout.write(self.style.ERROR('Deletion cancelled. Use --confirm flag to proceed.'))
            return

        # Proceed with deletion
        self.stdout.write('Starting deletion process...')

        try:
            with transaction.atomic():
                # Step 1: Restore stock quantities
                self.stdout.write('  • Restoring stock quantities...')
                for bill_item in bill_items:
                    bill_item.item.stock_quantity += bill_item.quantity
                    bill_item.item.save()

                # Step 2: Delete PDF files
                self.stdout.write('  • Deleting PDF files...')
                deleted_pdfs = 0
                for bill in bills:
                    if bill.pdf_file and os.path.exists(bill.pdf_file.path):
                        try:
                            os.remove(bill.pdf_file.path)
                            deleted_pdfs += 1
                        except OSError as e:
                            self.stdout.write(
                                self.style.WARNING(f'    Could not delete PDF for bill {bill.id}: {e}')
                            )

                # Step 3: Reset customer due amounts
                self.stdout.write('  • Resetting customer due amounts...')
                customers_to_reset = Customer.objects.filter(id__in=bills.values_list('customer', flat=True))
                reset_count = 0
                for customer in customers_to_reset:
                    # Calculate what the customer's due should be without these bills
                    remaining_bills = Bill.objects.filter(customer=customer).exclude(id__in=bills.values_list('id', flat=True))
                    if remaining_bills.exists():
                        total_remaining = sum(bill.total_amount + bill.op_due_amount for bill in remaining_bills)
                        customer.due = total_remaining
                    else:
                        customer.due = 0
                    customer.last_paid_balance = 0
                    customer.save()
                    reset_count += 1

                # Step 4: Delete bill items first (due to foreign key constraints)
                self.stdout.write('  • Deleting bill items...')
                bill_items.delete()

                # Step 5: Delete bills
                self.stdout.write('  • Deleting bills...')
                bills.delete()

                # Success message
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('✅ SUCCESS: All bills have been deleted!'))
                self.stdout.write('Summary:')
                self.stdout.write(f'  • Deleted {bill_count} bills')
                self.stdout.write(f'  • Deleted {bill_items_count} bill items')
                self.stdout.write(f'  • Deleted {deleted_pdfs} PDF files')
                self.stdout.write(f'  • Reset due amounts for {reset_count} customers')
                self.stdout.write(f'  • Restored stock for {bill_items_count} items')
                self.stdout.write('')
                self.stdout.write(self.style.WARNING('⚠️  Note: Customer monthly purchase data may need to be recalculated.'))

        except Exception as e:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(f'❌ ERROR: Deletion failed: {str(e)}'))
            self.stdout.write(self.style.ERROR('All changes have been rolled back.'))
            raise
