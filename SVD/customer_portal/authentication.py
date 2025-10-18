from django.contrib.auth.backends import BaseBackend
from milk_agency.models import Customer
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password

class CustomerBackend(BaseBackend):
    """
    Custom authentication backend for Customer model.
    Allows customers to authenticate using phone number and password.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            customer = Customer.objects.get(phone=username)
        except Customer.DoesNotExist:
            return None

        # First, try the normal password check
        if customer.check_password(password):
            # Update last login timestamp
            customer.last_login = timezone.now()
            customer.save(update_fields=['last_login'])
            return customer

        # If password check fails, check if the stored password is plain text
        # Django password hashes start with specific prefixes
        if not customer.password.startswith(('pbkdf2_sha256$', 'pbkdf2_sha1$', 'bcrypt$', 'sha1$', 'md5$', 'crypt$')):
            # Assume it's plain text and check directly
            if customer.password == password:
                # Hash the password and save it
                customer.set_password(password)
                customer.save()
                return customer
        return None

    def get_user(self, user_id):
        try:
            return Customer.objects.get(pk=user_id)
        except Customer.DoesNotExist:
            return None
