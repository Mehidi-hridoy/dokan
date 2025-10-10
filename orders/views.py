from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from products.models import Product
from orders.models import Order, OrderItem
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from orders.models import Order, OrderItem

def _calculate_order_total(order):
    """Helper function to calculate order total"""
    total = sum(item.get_total() for item in order.order_items.all())
    order.total = total
    order.save()
    return order

@login_required
def view_cart(request):
    order = Order.objects.filter(user=request.user, order_status='pending').first()
    
    # Recalculate total to ensure it's up to date
    if order:
        order = _calculate_order_total(order)
    
    context = {
        'order': order,
        'order_items': order.order_items.select_related('product').all() if order else [],
    }
    return render(request, 'orders/cart.html', context)

@require_POST
@login_required
def update_cart(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    action = request.POST.get('action')
    
    if action == 'increase':
        item.quantity += 1
    elif action == 'decrease' and item.quantity > 1:
        item.quantity -= 1
    
    item.save()
    
    # Recalculate order total after update
    order = item.order
    _calculate_order_total(order)
    
    messages.success(request, "Cart updated successfully!")
    return redirect('orders:view_cart')

@require_POST
@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    order = item.order
    item.delete()
    
    # Recalculate order total after removal
    _calculate_order_total(order)
    
    messages.success(request, "Item removed from cart!")
    return redirect('orders:view_cart')

def checkout(request):
    order = Order.objects.filter(user=request.user, order_status='pending').first()
    
    # Handle GET request - show checkout page
    if request.method == 'GET':
        if not order or not order.order_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('products:product_list')
        
        context = {
            'order': order,
            'order_items': order.order_items.select_related('product').all(),
        }
        return render(request, 'orders/checkout.html', context)
    
    # Handle POST request - process checkout
    elif request.method == 'POST':
        if not order or not order.order_items.exists():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': "Your cart is empty."}, status=400)
            messages.error(request, "Your cart is empty.")
            return redirect('products:product_list')

        shipping_address = request.POST.get('shipping_address')
        phone_number = request.POST.get('phone_number')
        payment_method = request.POST.get('payment_method')

        if not all([shipping_address, phone_number, payment_method]):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': "Please fill all required fields."}, status=400)
            messages.error(request, "Please fill all required fields.")
            return redirect('orders:checkout')

        # Update order with checkout information
        order.shipping_address = shipping_address
        order.phone_number = phone_number
        order.payment_method = payment_method
        order.order_status = 'completed'
        order.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True, 
                'message': "Order placed successfully!", 
                'redirect': '/orders/history/'
            })
        
        messages.success(request, "Order placed successfully!")
        return redirect('products:order_history')
    

    item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    action = request.POST.get('action')
    
    if action == 'increase':
        item.quantity += 1
    elif action == 'decrease' and item.quantity > 1:
        item.quantity -= 1
    
    item.save()
    return redirect('orders:view_cart')


    item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    item.delete()
    return redirect('orders:view_cart')