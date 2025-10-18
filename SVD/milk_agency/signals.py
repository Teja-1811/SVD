from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Bill
from .customer_monthly_purchase_calculator import CustomerMonthlyPurchaseCalculator

@receiver(post_save, sender=Bill)
def update_monthly_purchase_on_bill_save(sender, instance, created, **kwargs):
    """
    Signal to update customer monthly purchase records when a bill is saved
    """
    # Process both new bills and updates
    bill_date = instance.invoice_date
    year = bill_date.year
    month = bill_date.month

    try:
        # Update the monthly purchase record for this customer
        CustomerMonthlyPurchaseCalculator.calculate_customer_monthly_purchase(
            instance.customer, year, month
        )
    except Exception as e:
        pass
