# products/templatetags/product_extras.py
from django import template

register = template.Library()

@register.filter
def discount_percentage(product):
    if product.base_price and product.current_price < product.base_price:
        return round((product.base_price - product.current_price) / product.base_price * 100)
    return 0


# products/templatetags/product_extras.py
from django import template

register = template.Library()

@register.filter
def split_by(value, sep=','):
    if value:
        return [v.strip() for v in value.split(sep)]
    return []
