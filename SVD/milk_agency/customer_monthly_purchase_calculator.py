from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime, date
from .models import Customer, Bill, BillItem, CustomerMonthlyPurchase
from decimal import Decimal
import calendar

class CustomerMonthlyPurchaseCalculator:
    """
    Utility class to calculate and manage customer monthly purchase data
    """

    @staticmethod
    def calculate_customer_monthly_purchase(customer, year, month):
        """
        Calculate monthly purchase volume for a specific customer

        Args:
            customer: Customer object
            year: Year for calculation
            month: Month for calculation (1-12)

        Returns:
            dict: Dictionary containing milk, curd, and bi-product volumes
        """
        # Get the first and last day of the month
        last_day = calendar.monthrange(year, month)[1]
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        # Get all bills for the customer in the specified month
        bills = Bill.objects.filter(
            customer=customer,
            invoice_date__year=year,
            invoice_date__month=month
        )

        milk_volume = Decimal('0.00')
        curd_volume = Decimal('0.00')

        # Calculate purchase volumes from all bills
        for bill in bills:
            for bill_item in bill.items.all():
                item_code = bill_item.item.code.lower() if bill_item.item.code else ''
                item_quantity = Decimal(str(bill_item.quantity))
                item_category = bill_item.item.category.lower() if bill_item.item.category else ''

                # Extract volume from item code (e.g., "fcm500" -> 500)
                volume = 0
                if item_code:
                    # Extract digits from the item code
                    digits = ''.join(filter(str.isdigit, item_code))
                    if digits:
                        volume = int(digits)

                # Multiply by quantity to get total volume for this item
                total_item_volume = volume * item_quantity
                total_item_volume /= 1000  # Convert ml to liters

                # Categorize items based on their codes and categories
                if 'milk' in item_code or 'milk' in item_category:
                    milk_volume += total_item_volume
                elif 'curd' in item_code or 'curd' in item_category:
                    curd_volume += total_item_volume

        # Update or create the monthly purchase record
        monthly_purchase, created = CustomerMonthlyPurchase.objects.update_or_create(
            customer=customer,
            year=year,
            month=month,
            defaults={
                'milk_volume': milk_volume,
                'curd_volume': curd_volume,
            }
        )


        return {
            'milk_volume': milk_volume,
            'curd_volume': curd_volume,
        }

    @staticmethod
    def calculate_all_customers_monthly_purchase(year, month):
        """
        Calculate monthly purchase volumes for all customers

        Args:
            year: Year for calculation
            month: Month for calculation (1-12)

        Returns:
            dict: Dictionary mapping customer IDs to purchase volumes
        """
        customers = Customer.objects.all()
        results = {}

        for customer in customers:
            purchase_volume = CustomerMonthlyPurchaseCalculator.calculate_customer_monthly_purchase(
                customer, year, month
            )
            results[customer.id] = {
                'customer': customer,
                'purchase_volume': purchase_volume
            }

        return results

    @staticmethod
    def update_customer_monthly_purchase_records(year, month):
        """
        Update or create CustomerMonthlyPurchase records for all customers

        Args:
            year: Year for update
            month: Month for update (1-12)

        Returns:
            int: Number of records updated/created
        """
        customers_data = CustomerMonthlyPurchaseCalculator.calculate_all_customers_monthly_purchase(year, month)
        records_processed = 0

        for customer_id, data in customers_data.items():
            customer = data['customer']
            purchase_data = data['purchase_volume']

            # Update or create the monthly purchase record
            monthly_purchase, created = CustomerMonthlyPurchase.objects.update_or_create(
                customer=customer,
                year=year,
                month=month,
                defaults={
                    'milk_volume': purchase_data['milk_volume'],
                    'curd_volume': purchase_data['curd_volume'],
                }
            )

            records_processed += 1

        return records_processed

    @staticmethod
    def get_customer_monthly_summary(customer, start_year=None, start_month=None, end_year=None, end_month=None):
        """
        Get monthly purchase summary for a customer over a date range

        Args:
            customer: Customer object
            start_year: Start year (default: current year - 1)
            start_month: Start month (default: 1)
            end_year: End year (default: current year)
            end_month: End month (default: current month)

        Returns:
            list: List of monthly purchase data dictionaries
        """
        now = timezone.now()
        if start_year is None:
            start_year = now.year - 1
        if start_month is None:
            start_month = 1
        if end_year is None:
            end_year = now.year
        if end_month is None:
            end_month = now.month

        monthly_data = []

        # Get all monthly purchase records for the customer in the date range
        monthly_purchases = CustomerMonthlyPurchase.objects.filter(
            customer=customer,
            year__gte=start_year,
            year__lte=end_year
        ).order_by('year', 'month')

        # Filter by month range for start and end years
        monthly_purchases = monthly_purchases.filter(
            Q(year__gt=start_year) |
            Q(year=start_year, month__gte=start_month)
        ).filter(
            Q(year__lt=end_year) |
            Q(year=end_year, month__lte=end_month)
        )

        for purchase in monthly_purchases:
            monthly_data.append({
                'year': purchase.year,
                'month': purchase.month,
                'month_name': calendar.month_name[purchase.month],
                'purchase_volume': purchase.total_purchase_volume,
                'record': purchase
            })

        return monthly_data

    @staticmethod
    def generate_monthly_purchase_report(year, month, include_zero_purchases=False):
        """
        Generate a comprehensive monthly purchase report

        Args:
            year: Year for report
            month: Month for report (1-12)
            include_zero_purchases: Whether to include customers with zero purchases

        Returns:
            dict: Report data including customer purchase details
        """
        customers_data = CustomerMonthlyPurchaseCalculator.calculate_all_customers_monthly_purchase(year, month)

        report_data = {
            'year': year,
            'month': month,
            'month_name': calendar.month_name[month],
            'total_customers': 0,
            'active_customers': 0,
            'total_purchase_volume': Decimal('0.00'),
            'customers': []
        }

        for customer_id, data in customers_data.items():
            purchase_volume_data = data['purchase_volume']
            total_volume = purchase_volume_data['milk_volume'] + purchase_volume_data['curd_volume']

        # Sort customers by purchase volume (descending)
        report_data['customers'].sort(key=lambda x: x['purchase_volume'], reverse=True)

        return report_data

    @staticmethod
    def get_top_customers_by_purchase(year=None, month=None, limit=10):
        """
        Get top customers by purchase volume for a specific month or all time

        Args:
            year: Year for filtering (None for all time)
            month: Month for filtering (None for all time)
            limit: Number of top customers to return

        Returns:
            list: List of top customers with purchase data
        """
        if year is not None and month is not None:
            # Specific month
            purchases = CustomerMonthlyPurchase.objects.filter(
                year=year,
                month=month,
                total_purchase_volume__gt=0
            ).select_related('customer').order_by('-total_purchase_volume')[:limit]
        else:
            # All time - aggregate by customer
            from django.db.models import Sum
            purchases = CustomerMonthlyPurchase.objects.values('customer').annotate(
                total_purchase=Sum('total_purchase_volume')
            ).filter(total_purchase__gt=0).order_by('-total_purchase')[:limit]

            # Get customer objects for the aggregated results
            customer_ids = [p['customer'] for p in purchases]
            customers = Customer.objects.in_bulk(customer_ids)

            purchases = [
                {
                    'customer': customers[p['customer']],
                    'total_purchase_volume': p['total_purchase']
                }
                for p in purchases
            ]

        return purchases


# Convenience functions
def update_monthly_purchase_records(year, month):
    """Convenience function for updating all records"""
    return CustomerMonthlyPurchaseCalculator.update_customer_monthly_purchase_records(year, month)
