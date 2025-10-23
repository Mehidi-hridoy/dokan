# users/context_processors.py
from django.shortcuts import get_object_or_404
from orders.models import Order  # Adjust this import based on your app structure

def user_orders(request):
    """
    Context processor to make user orders available in all templates
    """
    context = {}
    
    if request.user.is_authenticated:
        try:
            # Get recent orders for the logged-in user
            # Adjust this query based on your actual Order model
            orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]
            context['user_orders'] = orders
        except Exception as e:
            # If there's any error (e.g., Order model doesn't exist yet), return empty list
            print(f"Error in user_orders context processor: {e}")
            context['user_orders'] = []
    else:
        context['user_orders'] = []
    
    return context