from django.db import models
from django.utils import timezone

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    buying_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Maximum Retail Price')
    stock_quantity = models.IntegerField(default=0)

    def __str__(self):
        return self.name

class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15, unique=True)
    address = models.TextField(blank=True, null=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.name} ({self.phone})"

class Sale(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Last paid amount for this sale")
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total profit from this sale")

    def __str__(self):
        customer_name = self.customer.name if self.customer else "Anonymous"
        return f"Invoice {self.invoice_number} - {customer_name}"

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity = models.IntegerField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

class BankBalance(models.Model):
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"Bank Balance: ₹{self.amount}"

class CashbookEntry(models.Model):
    c500 = models.IntegerField(default=0)
    c200 = models.IntegerField(default=0)
    c100 = models.IntegerField(default=0)
    c50 = models.IntegerField(default=0)

class Investment(models.Model):
    CATEGORY_CHOICES = [
        ('Kasi Agency', 'Kasi Agency'),
        ('HUL', 'HUL'),
        ('ITC', 'ITC'),
        ('Best Price', 'Best Price'),
        ('Jio Mart', 'Jio Mart'),
        ('Coco Cola', 'Coco Cola'),
        ('Campa', 'Campa'),
        ('Cigarettes', 'Cigarettes'),
        ('Petrol', 'Petrol'),
        ('Others', 'Others'),
    ]

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.category} - ₹{self.amount} - {self.date}"

class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('petrol', 'Petrol'),
        ('food', 'Food'),
        ('others', 'Others')
    ]

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.category} - ₹{self.amount} - {self.date}"
