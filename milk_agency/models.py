from django.db import models
from django.utils import timezone
from django.contrib.auth.models import (
    AbstractBaseUser, PermissionsMixin, BaseUserManager
)

# -----------------------------
# Custom User Manager
# -----------------------------
class CustomerManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Phone number is required")

        phone = str(phone).strip()
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("name", "Admin")

        return self.create_user(phone, password, **extra_fields)


# -----------------------------
# Custom User Model (Customer)
# -----------------------------
class Customer(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=20, unique=True, help_text="Phone number for login")
    name = models.CharField(max_length=255)
    shop_name = models.CharField(max_length=255, blank=True, help_text="Name of the customer's shop")
    retailer_id = models.CharField(max_length=100, blank=True, help_text="Unique identifier for the retailer")
    flat_number = models.CharField(max_length=255, blank=True)
    area = models.CharField(max_length=255, blank=True)
    pin_code = models.CharField(max_length=10, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)

    # Financial fields
    due = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Customer's current balance")

    # Commission eligibility
    is_commissioned = models.BooleanField(default=False, help_text="Whether this customer is eligible for commission calculation")

    # Delivery eligibility
    is_delivery = models.BooleanField(default=False, help_text="Whether this customer is eligible for delivery")

    # Status
    frozen = models.BooleanField(default=False)
    last_login = models.DateTimeField(blank=True, null=True)

    # Django-required fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Needed to access admin site

    objects = CustomerManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["name"]

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customer_groups',
        blank=True,
        help_text='The groups this customer belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customer_permissions',
        blank=True,
        help_text='Specific permissions for this customer.',
        verbose_name='user permissions',
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.phone})"

    # Optional convenience methods
    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

class Company(models.Model):
    name = models.CharField(max_length=255, unique=True)
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    website_link = models.URLField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Item(models.Model):
    code = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text='Unique item code')
    name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    category = models.CharField(max_length=100, blank=True, null=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    buying_price  = models.DecimalField(max_digits=10, decimal_places=2)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Maximum Retail Price')
    stock_quantity = models.IntegerField(default=0)
    pcs_count = models.IntegerField(default=0, help_text='Number of pieces per unit')
    image = models.ImageField(upload_to='items_saved/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    frozen = models.BooleanField(default=False, help_text='If true, item is frozen and not displayed in app except items dashboard')

    def __str__(self):
        return f"{self.code} - {self.name}" if self.code else self.name

class Bill(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='bills')
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    op_due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Last paid amount for this bill")
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total profit from this bill")
    commission_deducted = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Commission amount deducted from this bill")
    commission_month = models.IntegerField(null=True, blank=True, help_text="Month for which commission was deducted")
    commission_year = models.IntegerField(null=True, blank=True, help_text="Year for which commission was deducted")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        customer_name = self.customer.name if self.customer else "Anonymous"
        return f"Invoice {self.invoice_number} - {customer_name}"

class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity = models.IntegerField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.item.name} x {self.quantity}"

class BankBalance(models.Model):
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"Bank Balance: ₹{self.amount}"

class CashbookEntry(models.Model):
    c500 = models.IntegerField(default=0)
    c200 = models.IntegerField(default=0)
    c100 = models.IntegerField(default=0)
    c50 = models.IntegerField(default=0)
    c20 = models.IntegerField(default=0)
    c10 = models.IntegerField(default=0)
    coin20 = models.IntegerField(default=0)
    coin10 = models.IntegerField(default=0)
    coin5 = models.IntegerField(default=0)
    coin2 = models.IntegerField(default=0)
    coin1 = models.IntegerField(default=0)

class DailyPayment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='daily_payments')
    date = models.DateField()
    invoice_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        unique_together = ('company', 'date')
    def __str__(self):
        return f"{self.company} - {self.date} - Invoice: ₹{self.invoice_amount} Paid: ₹{self.paid_amount}"

class MonthlyPaymentSummary(models.Model):
    year = models.IntegerField()
    month = models.IntegerField()
    total_invoice = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ('year', 'month')

    def __str__(self):
        return f"{self.month}/{self.year} - Invoice: ₹{self.total_invoice}, Paid: ₹{self.total_paid}, Due: ₹{self.total_due}"

class DailySalesSummary(models.Model):
    date = models.DateField(default=timezone.now)
    retailer_id = models.CharField(max_length=100, help_text="Unique identifier for the retailer")
    retailer_name = models.CharField(max_length=255, blank=True, help_text="Name of the retailer")

    # Item tracking fields - will be updated dynamically
    item_names = models.TextField(blank=True, help_text="Comma-separated list of all items sold")
    item_quantities = models.TextField(blank=True, help_text="Comma-separated quantities for each item")
    item_prices = models.TextField(blank=True, help_text="Comma-separated prices for each item")

    # Calculated fields
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Additional tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('date', 'retailer_id')
        ordering = ['-date', 'retailer_id']

    def __str__(self):
        return f"{self.date} - {self.retailer_id} - ₹{self.total_amount}"

    def get_item_list(self):
        """Return list of items as dictionary"""
        if not self.item_names:
            return []

        names = self.item_names.split(',')
        quantities = self.item_quantities.split(',') if self.item_quantities else []
        prices = self.item_prices.split(',') if self.item_prices else []

        items = []
        for i, name in enumerate(names):
            items.append({
                'name': name.strip(),
                'quantity': float(quantities[i]) if i < len(quantities) else 0,
                'price': float(prices[i]) if i < len(prices) else 0
            })
        return items

    def set_items(self, items_list):
        """Set items from list of dictionaries"""
        names = []
        quantities = []
        prices = []

        for item in items_list:
            names.append(item['name'])
            quantities.append(str(item.get('quantity', 0)))
            prices.append(str(item.get('price', 0)))

        self.item_names = ','.join(names)
        self.item_quantities = ','.join(quantities)
        self.item_prices = ','.join(prices)

# CustomerMonthlyPurchase model removed - functionality replaced with direct calculations from Bill and BillItem models

class CustomerMonthlyCommission(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='monthly_commissions')
    year = models.IntegerField()
    month = models.IntegerField()
    milk_volume = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Average daily milk volume")
    curd_volume = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Average daily curd volume")
    total_volume = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Average daily total volume")
    milk_commission_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Commission rate for milk per liter")
    curd_commission_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Commission rate for curd per liter")
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total commission amount for the month")
    status = models.BooleanField(default=False, help_text="Whether the commission has been deducted from a bill")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('customer', 'year', 'month')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.customer.name} - {self.month}/{self.year} - Commission: ₹{self.commission_amount}"



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

class Contact(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"

class CustomerPayment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True)
    method = models.CharField(max_length=20)  # UPI
    status = models.CharField(max_length=20)  # SUCCESS / FAILED
    created_at = models.DateTimeField(auto_now_add=True)
