from django.core.management.base import BaseCommand
from django.utils import timezone
from milk_agency.models import Bill, BillItem

class Command(BaseCommand):
    help = 'Deletes all bills created on the current date'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        bills = Bill.objects.filter(invoice_date=today)
        count = bills.count()

        if count == 0:
            self.stdout.write(self.style.WARNING('No bills found for today.'))
            return

        # Delete bill items first
        bill_items = BillItem.objects.filter(bill__in=bills)
        bill_items_count = bill_items.count()
        bill_items.delete()

        # Delete bills
        bills.delete()

        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} bills and {bill_items_count} bill items created today.'))
