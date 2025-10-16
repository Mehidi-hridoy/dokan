# Assuming 'your_app' is where you place this file (e.g., 'orders')

def cart_count_processor(request):
    """Adds the total item count in the cart to the context."""
    cart = request.session.get('cart', {})
    cart_count = sum(item.get('quantity', 0) for item in cart.values())
    
    return {
        'cart_count': cart_count,
    }