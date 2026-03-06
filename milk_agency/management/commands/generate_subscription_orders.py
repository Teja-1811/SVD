from django.core.management.base import BaseCommand
from milk_agency.utils.subscription_engine import generate_daily_subscription_orders


class Command(BaseCommand):

    help = "Generate daily subscription delivery orders"

    def handle(self, *args, **kwargs):

        created = generate_daily_subscription_orders()

        self.stdout.write(
            self.style.SUCCESS(
                f"{created} subscription orders generated successfully."
            )
        )