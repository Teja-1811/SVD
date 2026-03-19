from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date

from milk_agency.subscription_billing import generate_subscription_delivery_bills


class Command(BaseCommand):
    help = "Generate daily subscription orders and create/link bills for subscription deliveries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Optional target date in YYYY-MM-DD format.",
        )

    def handle(self, *args, **options):
        raw_date = options.get("date")
        target_date = parse_date(raw_date) if raw_date else None

        if raw_date and target_date is None:
            self.stderr.write(self.style.ERROR("Invalid --date. Use YYYY-MM-DD."))
            return

        result = generate_subscription_delivery_bills(target_date=target_date)
        self.stdout.write(
            self.style.SUCCESS(
                f"Subscription delivery billing complete for {result['date']}: "
                f"{result['created_bills']} bill(s) created, "
                f"{result['linked_deliveries']} delivery link(s) updated."
            )
        )
