from django import template
from django.http import QueryDict

register = template.Library()

@register.filter
def remove_query_param(query_string, param_name):
    """
    Removes a single parameter from the given query string.
    Usage: {{ request.GET.urlencode|remove_query_param:"page" }}
    """
    if not query_string:
        return ""
    
    q = QueryDict(query_string, mutable=True)
    if param_name in q:
        del q[param_name]
    return q.urlencode()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


