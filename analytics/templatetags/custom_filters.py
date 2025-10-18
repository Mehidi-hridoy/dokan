from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def div(value, arg):
    """Divides the value by the argument."""
    try:
        if arg:
            return Decimal(value) / Decimal(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        pass
    return 0

@register.filter
def mul(value, arg):
    """Multiplies the value by the argument."""
    try:
        return Decimal(value) * Decimal(arg)
    except (ValueError, TypeError):
        pass
    return 0