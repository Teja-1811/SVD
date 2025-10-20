from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary with key"""
    if dictionary is None:
        return {}
    return dictionary.get(key, {})

@register.filter
def get_nested_item(item_dict, date_key):
    """Get quantity for specific date from item dictionary"""
    if item_dict is None:
        return 0
    return item_dict.get(date_key, 0)

@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sub(value, arg):
    """Subtract arg from value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0
