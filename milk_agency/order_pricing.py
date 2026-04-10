from decimal import Decimal

from milk_agency.models import Item

DELIVERY_CHARGE_AMOUNT = Decimal("5.00")
DELIVERY_ITEM_CODE = "DELIVERY_CHARGE"
TAKEAWAY_ALIASES = ("takeaway", "take away", "pickup", "pick up", "self pickup", "self-pickup")


def get_customer_unit_price(item, customer):
    if customer and getattr(customer, "user_type", "").lower() == "user":
        return Decimal(item.mrp or item.selling_price or 0)
    return Decimal(item.selling_price or 0)


def is_takeaway_address(address):
    normalized = (address or "").strip().lower()
    return normalized in TAKEAWAY_ALIASES


def get_delivery_charge_amount(customer=None, address=None):
    if customer and getattr(customer, "user_type", "").lower() == "user" and not is_takeaway_address(address):
        return DELIVERY_CHARGE_AMOUNT
    return Decimal("0.00")


def get_or_create_delivery_charge_item():
    delivery_item, _ = Item.objects.get_or_create(
        code=DELIVERY_ITEM_CODE,
        defaults={
            "name": "Delivery Charge",
            "selling_price": DELIVERY_CHARGE_AMOUNT,
            "buying_price": Decimal("0.00"),
            "mrp": DELIVERY_CHARGE_AMOUNT,
            "stock_quantity": 0,
            "pcs_count": 0,
            "category": "Service",
            "description": "Fixed delivery charge for user home delivery orders",
        },
    )
    return delivery_item
