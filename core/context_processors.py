from products.models import Category
from django.conf import settings

def global_settings(request):
    categories = Category.objects.filter(is_active=True, parent__isnull=True)
    
    return {
        'categories': categories,
        'DOKAN_VERSION': getattr(settings, 'DOKAN_VERSION', '2.01'),
    }