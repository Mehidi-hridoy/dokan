from django import template
from orders.models import Order
from products.models import Product

register = template.Library()

@register.simple_tag(takes_context=True)
def get_cart_count(context):
    request = context['request']
    cart_count = 0
    
    if request.user.is_authenticated:
        try:
            order = Order.objects.get(user=request.user, order_status='pending')
            cart_count = order.items.count()
        except Order.DoesNotExist:
            cart_count = 0
    else:
        session_cart = request.session.get('cart', {})
        cart_count = len(session_cart)
    
    return cart_count

@register.simple_tag(takes_context=True)
def get_cart_total(context):
    request = context['request']
    total = 0
    
    if request.user.is_authenticated:
        try:
            order = Order.objects.get(user=request.user, order_status='pending')
            total = order.total
        except Order.DoesNotExist:
            total = 0
    else:
        session_cart = request.session.get('cart', {})
        for product_id, item_data in session_cart.items():
            try:
                product = Product.objects.get(id=product_id, is_active=True)
                total += item_data['quantity'] * product.price
            except Product.DoesNotExist:
                continue
    
    return total

@register.simple_tag(takes_context=True)
def get_cart_items(context):
    request = context['request']
    cart_items = []
    
    if request.user.is_authenticated:
        try:
            order = Order.objects.get(user=request.user, order_status='pending')
            cart_items = list(order.items.select_related('product').all())
        except Order.DoesNotExist:
            cart_items = []
    else:
        session_cart = request.session.get('cart', {})
        for product_id, item_data in session_cart.items():
            try:
                product = Product.objects.get(id=product_id, is_active=True)
                cart_items.append({
                    'product': product,
                    'quantity': item_data['quantity'],
                    'total': item_data['quantity'] * product.price,
                    'color': item_data.get('color'),
                    'size': item_data.get('size'),
                })
            except Product.DoesNotExist:
                continue
    
    return cart_items