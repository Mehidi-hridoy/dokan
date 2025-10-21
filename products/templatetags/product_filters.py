from django import template

register = template.Library()

@register.simple_tag
def modify_query_string(request, key, value):
    """
    Modify a query string parameter while preserving others
    """
    params = request.GET.copy()
    
    if value is None:
        if key in params:
            del params[key]
    else:
        params[key] = value
    
    return params.urlencode()