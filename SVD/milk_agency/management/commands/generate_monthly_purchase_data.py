from django.core.management.base import BaseCommand
from milk_agency.customer_monthly_purchase_calculator import update_monthly_purchase_records
from datetime import datetime
from django.utils import timezone

class Command(BaseCommand):
    help = 'Generate monthly purchase data for a specified month and year. Use --current to generate for the current month, or --all-months to generate for all months in the specified year.'

    def add_arguments(self, parser):
        parser.add_argument('year', nargs='?', type=int, default=None, help='Year for which to generate data (required unless --current is used)')
        parser.add_argument('month', nargs='?', type=int, default=None, help='Month for which to generate data (1-12, required unless --current or --all-months is used)')
        parser.add_argument('--current', action='store_true', help='Generate data for the current month and year')
        parser.add_argument('--all-months', action='store_true', help='Generate data for all months in the specified year')
        parser.add_argument('--dry-run', action='store_true', help='Simulate the generation without updating records')

    def handle(self, *args, **kwargs):
        current_year = timezone.now().year
        current_month = timezone.now().month
        
        if kwargs['current']:
            year = current_year
            month = current_month
            self.stdout.write(f"Generating data for current month: {datetime(year, month, 1).strftime('%B %Y')}")
        elif kwargs['all_months']:
            if not kwargs['year']:
                self.stderr.write(self.style.ERROR('Year is required when using --all-months'))
                return
            year = kwargs['year']
            total_updated = 0
            for month in range(1, 13):
                if kwargs['dry_run']:
                    self.stdout.write(f"Dry run: Would generate data for {datetime(year, month, 1).strftime('%B %Y')}")
                else:
                    records_updated = update_monthly_purchase_records(year, month)
                    total_updated += records_updated
                    self.stdout.write(self.style.SUCCESS(f"Generated data for {datetime(year, month, 1).strftime('%B %Y')}. Records updated: {records_updated}"))
            if not kwargs['dry_run']:
                self.stdout.write(self.style.SUCCESS(f"Total records updated for year {year}: {total_updated}"))
            return
        else:
            if not kwargs['year'] or not kwargs['month']:
                self.stderr.write(self.style.ERROR('Year and month are required when not using --current or --all-months'))
                return
            year = kwargs['year']
            month = kwargs['month']
            self.stdout.write(f"Generating data for {datetime(year, month, 1).strftime('%B %Y')}")

        if kwargs['dry_run']:
            self.stdout.write(f"Dry run: Would generate data for {datetime(year, month, 1).strftime('%B %Y')}")
        else:
            # Call the function to update monthly purchase records
            records_updated = update_monthly_purchase_records(year, month)
            self.stdout.write(self.style.SUCCESS(f"Monthly purchase data generated for {datetime(year, month, 1).strftime('%B %Y')}. Records updated: {records_updated}"))
