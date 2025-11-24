from django.db import models
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from milk_agency.models import Customer, Item


class CustomerOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('ready', 'Ready for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ]

    order_number = models.CharField(max_length=50, unique=True, help_text='Unique order number')
    order_date = models.DateTimeField(default=timezone.now)
    delivery_date = models.DateField(blank=True, null=True, help_text='Requested delivery date')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, help_text='Admin notes and feedback')
    delivery_address = models.TextField(help_text='Delivery address')
    phone = models.CharField(max_length=20, blank=True, help_text='Contact phone for delivery')
    additional_notes = models.TextField(blank=True, help_text="Customer's additional notes")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Total order amount')
    approved_total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Admin approved total amount')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Foreign keys
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='created_orders')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name='approved_orders')

    class Meta:
        verbose_name = 'Customer Order'
        verbose_name_plural = 'Customer Orders'
        ordering = ['-order_date']

    def __str__(self):
        return f"Order {self.order_number} - {self.customer.name}"


class CustomerOrderItem(models.Model):
    order = models.ForeignKey(CustomerOrder, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    requested_quantity = models.IntegerField(help_text='Quantity requested by customer')
    requested_price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Price per unit requested')
    approved_quantity = models.IntegerField(default=0, help_text='Quantity approved by admin')
    approved_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Price per unit approved by admin')
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Discount per unit')
    # total discount for the line = discount * requested_quantity
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    admin_notes = models.TextField(blank=True, help_text='Admin notes for this item')
    requested_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    approved_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        return f"{self.item.name} x {self.requested_quantity}"
