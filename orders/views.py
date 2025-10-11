from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from products.models import Product
from orders.models import Order, OrderItem
from products.views import _calculate_order_total, _get_user_order, _get_session_cart


def view_cart(request):
    order = _get_user_order(request)
    cart_items, cart_total = _get_session_cart(request) if not request.user.is_authenticated else ([], 0)
    
    if order:
        order = _calculate_order_total(order)
    
    context = {
        'order': order,
        'order_items': order.order_items.select_related('product').all() if order else [],
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    return render(request, 'orders/cart.html', context)

@require_POST
def update_cart(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    action = request.POST.get('action')
    
    if action == 'increase':
        item.quantity += 1
    elif action == 'decrease' and item.quantity > 1:
        item.quantity -= 1
    
    item.save()
    order = _calculate_order_total(item.order)
    
    messages.success(request, "Cart updated successfully!")
    return redirect('orders:view_cart')

@require_POST
def remove_from_cart(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    order = item.order
    item.delete()
    
    order = _calculate_order_total(order)
    
    messages.success(request, "Item removed from cart!")
    return redirect('orders:view_cart')

# REMOVE @require_POST decorator from checkout function
def checkout(request):
    order = _get_user_order(request)
    cart_items, cart_total = _get_session_cart(request) if not request.user.is_authenticated else ([], 0)
    
    if request.method == 'GET':
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to proceed to checkout.")
            return redirect('login')
        if not order or not order.order_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('products:product_list')
        
        context = {
            'order': order,
            'order_items': order.order_items.select_related('product').all(),
            'cart_items': cart_items,
            'cart_total': cart_total,
        }
        return render(request, 'orders/checkout.html', context)
    
    elif request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'message': "Please log in to checkout."}, status=401)
        
        if not order or not order.order_items.exists():
            return JsonResponse({'success': False, 'message': "Your cart is empty."}, status=400)

        shipping_address = request.POST.get('shipping_address')
        phone_number = request.POST.get('phone_number')
        payment_method = request.POST.get('payment_method')

        if not all([shipping_address, phone_number, payment_method]):
            return JsonResponse({'success': False, 'message': "Please fill all required fields."}, status=400)

        order.shipping_address = shipping_address
        order.phone_number = phone_number
        order.payment_method = payment_method
        order.order_status = 'completed'
        order.save()

        return JsonResponse({
            'success': True, 
            'message': "Order placed successfully!", 
            'redirect': '/orders/history/'
        })