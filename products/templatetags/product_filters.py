# products/templatetags/product_filters.py
from django import template
from urllib.parse import urlencode

register = template.Library()

@register.simple_tag
def url_replace(request, **kwargs):
    query = request.GET.copy()
    for key, value in kwargs.items():
        if value is not None:
            query[key] = value
        else:
            query.pop(key, None)
    return query.urlencode()

@register.filter
def find_name_by_slug(categories, slug):
    for cat in categories:
        if cat.slug == slug:
            return cat.name
    return ""