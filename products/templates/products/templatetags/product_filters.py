from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, 0)

@register.filter
def get_by_slug(queryset, slug):
    try:
        return queryset.get(slug=slug)
    except:
        return None