from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from products.models import Product
from .models import Order, OrderItem

@login_required
def add_to_cart(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    if not product.is_in_stock:
        messages.error(request, f"{product.name} is out of stock.")
        return redirect('products:product_detail', slug=slug)

    order, created = Order.objects.get_or_create(
        user=request.user,
        is_completed=False,
        defaults={'total': 0}
    )

    color = request.POST.get('color')
    size = request.POST.get('size')
    weight = request.POST.get('weight')

    order_item, created = OrderItem.objects.get_or_create(
        order=order,
        product=product,
        color=color,
        size=size,
        weight=weight,
        defaults={'quantity': 1, 'price': product.price}
    )

    if not created:
        order_item.quantity += 1
        order_item.save()

    order.calculate_total()
    messages.success(request, f"{product.name} added to cart!")
    return redirect('products:product_detail', slug=slug)

@login_required
def view_cart(request):
    order = Order.objects.filter(user=request.user, is_completed=False).first()
    context = {
        'order': order,
        'order_items': order.order_items.all() if order else [],
    }
    return render(request, 'orders/cart.html', context)

@login_required
def checkout(request):
    order = Order.objects.filter(user=request.user, is_completed=False).first()
    if not order or not order.order_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('products:product_list')

    if request.method == 'POST':
        shipping_address = request.POST.get('address')
        phone_number = request.POST.get('phone_number')
        payment_method = request.POST.get('payment_method')

        order.shipping_address = shipping_address
        order.phone_number = phone_number
        order.payment_method = payment_method
        order.is_completed = True
        order.calculate_total()
        order.save()

        messages.success(request, "Order placed successfully!")
        return redirect('orders:order_history')

    context = {
        'order': order,
        'order_items': order.order_items.all(),
        'user': request.user,
    }
    return render(request, 'orders/checkout.html', context)

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user, is_completed=True).order_by('-created_at')
    context = {
        'orders': orders,
    }
    return render(request, 'orders/order_history.html', context)