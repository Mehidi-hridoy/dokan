from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from products.models import Product, Review
from store.models import Category, Brand
from orders.models import Order, OrderItem
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from decimal import Decimal  # ✅ Keep only this one
from .models import Product
from django.urls import reverse


def view_cart(request):
    """Display cart details for both authenticated and guest users"""

    if request.user.is_authenticated:
        order = _get_user_order(request)
        order_items = list(order.order_items.select_related('product').all()) if order else []
        cart_count = order.order_items.count() if order else 0
        subtotal = sum(item.unit_price * item.quantity for item in order_items) if order_items else Decimal('0')

        # Wrap for template compatibility
        cart_items = [
            {
                'product': item.product,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
                'color': item.color,
                'size': item.size,
                'weight': item.weight,
                'total': item.unit_price * item.quantity
            }
            for item in order_items
        ]
    
    else:
        order = None
        session_cart, cart_total = _get_session_cart(request)
        cart_items = []
        for item in session_cart:
            cart_items.append({
                'product': item['product'],
                'quantity': item['quantity'],
                'unit_price': item['product'].sale_price or item['product'].current_price,
                'color': item.get('color'),
                'size': item.get('size'),
                'weight': item.get('weight'),
                'total': item['total'],
            })
        cart_count = len(cart_items)
        subtotal = cart_total

    # Shipping, tax, total
    shipping_cost = Decimal('0') if subtotal >= Decimal('1000') else Decimal('50')
    tax_amount = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
    total = (subtotal + tax_amount + shipping_cost).quantize(Decimal('0.01'))

    context = {
        'order': order,
        'cart_items': cart_items,
        'cart_count': cart_count,
        'subtotal': subtotal,
        'tax_amount': tax_amount,
        'shipping_cost': shipping_cost,
        'total': total,
        'is_guest': not request.user.is_authenticated,
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


def add_to_cart(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    if not product.is_in_stock:
        return JsonResponse({'success': False, 'message': f"{product.products_name} is out of stock."}, status=400)

    color = request.POST.get('color')
    size = request.POST.get('size')
    weight = request.POST.get('weight')
    quantity = int(request.POST.get('quantity', 1))

    if request.user.is_authenticated:
        order = Order.objects.filter(user=request.user, order_status='pending').first()
        if not order:
            order = Order.objects.create(user=request.user, order_status='pending', total=0)
        
        order_item, created = OrderItem.objects.get_or_create(
            order=order,
            product=product,
            defaults={
                'quantity': quantity,
                'unit_price': product.sale_price or product.current_price,
                'original_unit_price': product.current_price,
            }
        )

        if not created:
            order_item.quantity += quantity
            order_item.save()
        
        _calculate_order_total(order)
        
        cart_count = order.order_items.count()
        
        return JsonResponse({
            'success': True,
            'message': f"{product.products_name} added to cart!",
            'cart_count': cart_count,
            'product_name': product.products_name,
            'product_image': product.products_image.url if product.products_image else None,
            'quantity': order_item.quantity,
            'subtotal': str(order_item.get_total()),
            'checkout_url': reverse('products:checkout')
        })
    else:
        # Handle anonymous user cart in session
        cart = request.session.get('cart', {})
        cart_key = f"{slug}_{color or ''}_{size or ''}_{weight or ''}"
        if cart_key in cart:
            cart[cart_key]['quantity'] += quantity
        else:
            cart[cart_key] = {
                'slug': slug,
                'quantity': quantity,
                'color': color,
                'size': size,
                'weight': weight
            }
        request.session['cart'] = cart
        request.session.modified = True
        
        cart_count = len(cart)
        
        return JsonResponse({
            'success': True,
            'message': f"{product.products_name} added to cart!",
            'cart_count': cart_count,
            'product_name': product.products_name,
            'product_image': product.products_image.url if product.products_image else None,
            'quantity': quantity,
            'subtotal': str((product.sale_price or product.current_price) * quantity),
            'checkout_url': reverse('products:checkout')
        })
    
def _calculate_order_total(order):
    """Helper function to calculate order total"""
    total = sum(item.get_total() for item in order.order_items.all())
    order.total = total
    order.save()
    return order

def checkout(request):
    """Checkout process for both authenticated and guest users"""
    if request.user.is_authenticated:
        # Authenticated user logic
        order = _get_user_order(request)
        if not order or not order.order_items.exists():
            messages.error(request, "Your cart is empty!")
            return redirect('products:view_cart')
    else:
        # Guest user logic - get cart from session
        cart_items, cart_total = _get_session_cart(request)
        if not cart_items:
            messages.error(request, "Your cart is empty!")
            return redirect('products:view_cart')
        
        # Create a temporary order for guest checkout
        order = Order.objects.create(
            order_status='pending',
            customer_name="Guest User",
            total=cart_total
        )
        
        # Add cart items to the order
        for cart_item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=cart_item['product'],
                quantity=cart_item['quantity'],
                unit_price=cart_item['unit_price'],
                original_unit_price=cart_item['product'].current_price,
                color=cart_item.get('color'),
                size=cart_item.get('size'),
                weight=cart_item.get('weight')
            )
        
        # Recalculate order total
        _calculate_order_total(order)
        
        # Store guest order ID in session
        request.session['guest_order_id'] = order.id

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # --- Update order with customer details ---
                order.customer_name = request.POST.get(
                    'customer_name',
                    f"{request.user.first_name} {request.user.last_name}".strip()
                    if request.user.is_authenticated else "Guest User"
                )
                order.phone_number = request.POST.get('phone_number', '')
                order.email = request.POST.get('email', 
                    request.user.email if request.user.is_authenticated else "")
                order.shipping_address = request.POST.get('shipping_address', '')
                order.billing_address = (
                    request.POST.get('billing_address', '')
                    or request.POST.get('shipping_address', '')
                )
                order.order_note = request.POST.get('order_note', '')
                order.payment_method = request.POST.get('payment_method', 'cash_on_delivery')
                order.delivery_area = request.POST.get('delivery_area', '')
                order.city = request.POST.get('city', '')
                order.zip_code = request.POST.get('zip_code', '')

                # --- Financial calculations using Decimals ---
                order.tax_amount = Decimal(request.POST.get('tax_amount', '0') or '0')
                order.shipping_cost = Decimal(request.POST.get('shipping_cost', '0') or '0')
                order.discount_amount = Decimal(request.POST.get('discount_amount', '0') or '0')

                # ✅ Compute subtotal safely from order items
                order.subtotal = sum(
                    (item.unit_price * item.quantity for item in order.order_items.all()),
                    Decimal('0')
                )

                # ✅ Compute total
                order.total = (
                    order.subtotal
                    + order.tax_amount
                    + order.shipping_cost
                    - order.discount_amount
                )

                # --- Update order statuses ---
                order.order_status = 'processed'
                order.payment_status = 'pending'

                # Auto-mark as paid if not COD
                if order.payment_method != 'cash_on_delivery':
                    order.payment_status = 'paid'
                    order.processed_at = timezone.now()

                order.save()

                # Clear guest user session data after successful order
                if not request.user.is_authenticated:
                    if 'cart' in request.session:
                        del request.session['cart']
                    if 'guest_order_id' in request.session:
                        del request.session['guest_order_id']

                messages.success(request, f'Order #{order.order_number} placed successfully!')

                # ✅ AJAX response for frontend
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Order #{order.order_number} placed successfully!',
                        'redirect': f'/thank-you/{order.id}/',
                        'order_id': order.id
                    })
                else:
                    return redirect('products:thank_you', order_id=order.id)

        except Exception as e:
            import traceback
            print("🧩 DEBUG TRACEBACK:", traceback.format_exc())
            messages.error(request, f'Error processing order: {str(e)}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
            else:
                return redirect('products:checkout')

    # --- Calculate totals for GET request ---
    if request.user.is_authenticated:
        subtotal = sum(
            (item.unit_price * item.quantity for item in order.order_items.all()),
            Decimal('0')
        )
    else:
        # For guest users, use the order we just created
        subtotal = sum(
            (item.unit_price * item.quantity for item in order.order_items.all()),
            Decimal('0')
        )

    shipping_cost = Decimal('0') if subtotal >= Decimal('1000') else Decimal('50')
    tax_amount = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
    total = (subtotal + tax_amount + shipping_cost).quantize(Decimal('0.01'))

    context = {
        'order': order,
        'subtotal': subtotal,
        'tax_amount': tax_amount,
        'shipping_cost': shipping_cost,
        'total': total,
        'is_guest': not request.user.is_authenticated,
    }

    return render(request, 'orders/checkout.html', context)

def thank_you(request, order_id):
    """Order thank you page for both authenticated and guest users"""
    if request.user.is_authenticated:
        order = get_object_or_404(Order, id=order_id, user=request.user)
    else:
        # For guest users, verify the order belongs to their session
        guest_order_id = request.session.get('guest_order_id')
        if guest_order_id != order_id:
            messages.error(request, "Order not found!")
            return redirect('products:home')
        order = get_object_or_404(Order, id=order_id)
    
    order_items = order.order_items.select_related('product').all()
    
    context = {
        'order': order,
        'order_items': order_items,
    }
    return render(request, 'products/thank_you.html', context)

@login_required
def order_history(request):
    completed_statuses = ['completed', 'delivered']
    orders = Order.objects.filter(
        user=request.user, 
        order_status__in=completed_statuses
    ).select_related('user').order_by('-created_at')
    
    cart_items, cart_total = _get_session_cart(request) if not request.user.is_authenticated else ([], 0)
    
    context = {
        'orders': orders,
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    return render(request, 'products/order_history.html', context)

def _calculate_discount(product):
    """Helper function to calculate discount percentage and tag list"""
    if product.base_price and product.base_price > product.sale_price:
        product.discount_percentage = round(
            ((product.base_price - product.sale_price) / product.base_price) * 100
        )
    else:
        product.discount_percentage = None
    product.tag_list = product.tags.split(', ') if product.tags else []
    return product

def _get_user_order(request):
    """Get or create a single pending order for authenticated user"""
    if request.user.is_authenticated:
        # Get the most recent pending order or create a new one
        order = Order.objects.filter(
            user=request.user,
            order_status='pending'
        ).order_by('-created_at').first()
        
        if not order:
            order = Order.objects.create(
                user=request.user,
                order_status='pending'
            )
        return order
    return None

def _get_session_cart(request):
    """Helper function to get cart items from session for anonymous users"""
    cart = request.session.get('cart', {})
    cart_items = []
    cart_total = Decimal('0.00')
    for key, details in cart.items():
        try:
            product = Product.objects.get(slug=details['slug'], is_active=True)
            if product.is_in_stock:
                unit_price = product.sale_price or product.current_price
                item_total = unit_price * details['quantity']
                cart_items.append({
                    'product': product,
                    'quantity': details['quantity'],
                    'color': details.get('color'),
                    'size': details.get('size'),
                    'weight': details.get('weight'),
                    'total': item_total,
                    'unit_price': unit_price
                })
                cart_total += item_total
        except Product.DoesNotExist:
            continue
    return cart_items, cart_total

def _merge_session_cart_to_order(request, user):
    """Merge session cart into user's order upon login"""
    if 'cart' in request.session:
        order = Order.objects.filter(user=user, order_status='pending').first()
        if not order:
            order = Order.objects.create(user=user, order_status='pending', total=0)
        
        cart = request.session.get('cart', {})
        for slug, details in cart.items():
            try:
                product = Product.objects.get(slug=slug, is_active=True)
                if product.is_in_stock:
                    order_item, created = OrderItem.objects.get_or_create(
                        order=order,
                        product=product,
                        color=details.get('color'),
                        size=details.get('size'),
                        weight=details.get('weight'),
                        defaults={'quantity': details['quantity'], 'price': product.price}
                    )
                    if not created:
                        order_item.quantity += details['quantity']
                        order_item.save()
            except Product.DoesNotExist:
                continue
        # Recalculate order total
        _calculate_order_total(order)
        # Clear session cart after merging
        request.session['cart'] = {}
        request.session.modified = True

@login_required
def add_review(request):
    """Handle adding a product review"""
    if request.method == 'POST':
        product_slug = request.POST.get('product_slug')
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '')
        title = request.POST.get('title', '')

        product = get_object_or_404(Product, slug=product_slug)

        # Check if user already reviewed (unique_together constraint)
        review, created = Review.objects.get_or_create(
            product=product,
            user=request.user,
            defaults={'rating': rating, 'comment': comment, 'title': title, 'created_at': timezone.now()}
        )
        if not created:
            # Update existing review
            review.rating = rating
            review.comment = comment
            review.title = title
            review.created_at = timezone.now()
            review.is_approved = False  # reset approval if updated
            review.save()

        messages.success(request, "Your review has been submitted!")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    return redirect('/')  # fallback for GET requests

def cart_dropdown_content(request):
    """Return cart content for dropdown"""
    if request.user.is_authenticated:
        order = _get_user_order(request)
        cart_items = []
        cart_total = Decimal('0.00')
    else:
        order = None
        cart_items, cart_total = _get_session_cart(request)
    
    context = {
        'order': order,
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    
    return render(request, 'includes/cart_dropdown_content.html', context)


