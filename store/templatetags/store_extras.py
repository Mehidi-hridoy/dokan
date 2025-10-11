from django import template
from store.models import Category, Brand

register = template.Library()

@register.simple_tag
def get_categories():
    """Get all active categories"""
    return Category.objects.filter(is_active=True).select_related('parent')

@register.simple_tag
def get_brands():
    """Get all active brands"""
    return Brand.objects.filter(is_active=True)

@register.simple_tag
def get_main_categories():
    """Get main categories (no parent)"""
    return Category.objects.filter(parent__isnull=True, is_active=True)

@register.simple_tag
def get_category_tree():
    """Get hierarchical category tree"""
    categories = Category.objects.filter(is_active=True).select_related('parent')
    
    def build_tree(parent=None):
        children = [cat for cat in categories if cat.parent == parent]
        return [
            {
                'category': child,
                'children': build_tree(child)
            }
            for child in children
        ]
    
    return build_tree()

@register.simple_tag
def get_featured_categories(limit=8):
    """Get featured categories (most products)"""
    return Category.objects.filter(
        is_active=True
    ).annotate(
        product_count=Count('products', filter=Q(products__is_active=True))
    ).order_by('-product_count')[:limit]

@register.simple_tag
def get_featured_brands(limit=8):
    """Get featured brands (with logos)"""
    return Brand.objects.filter(
        is_active=True,
        logo__isnull=False
    )[:limit]

@register.filter
def category_path(category):
    """Get full path for a category"""
    path = []
    current = category
    while current:
        path.insert(0, current.name)
        current = current.parent
    return ' → '.join(path)