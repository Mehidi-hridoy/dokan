from django import template
from urllib.parse import urlencode, parse_qs

register = template.Library()

@register.filter
def remove_query_param(querystring, param):
    query_dict = parse_qs(querystring)
    query_dict.pop(param, None)
    return urlencode(query_dict, doseq=True)

@register.filter
def lookup(dictionary, key):
    return dictionary.get(key)