# core/context_processors.py
from django.db import models
from django.contrib.admin.models import LogEntry

def admin_dashboard_data(request):
    """
    Modern context processor for admin dashboard data
    """
    if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
        return {}
    
    data = {
        'total_products': 0,
        'total_orders': 0,
        'pending_orders': 0,
        'low_stock_count': 0,
        'recent_logs': [],
    }
    
    try:
        from products.models import Product
        data['total_products'] = Product.objects.count()
    except Exception:
        pass
    
    try:
        from orders.models import Order
        data['total_orders'] = Order.objects.count()
        data['pending_orders'] = Order.objects.filter(order_status='pending').count()
    except Exception:
        pass
    
    try:
        from inventory.models import Inventory
        data['low_stock_count'] = Inventory.objects.filter(quantity__lt=5).count()
    except Exception:
        pass
    
    try:
        data['recent_logs'] = LogEntry.objects.select_related('user', 'content_type')[:10]
    except Exception:
        pass
    
    return data