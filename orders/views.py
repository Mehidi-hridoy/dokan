# orders/views.py
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.core.paginator import Paginator

from products.models import Product, Review
from orders.models import Order
from django.db.models import Q
from django.utils import timezone



def _calculate_discount(product: Product) -> Product:
    """Helper to calculate discount percentage and tag list."""
    if product.base_price and product.base_price > product.sale_price:
        product.discount_percentage = round(
            ((product.base_price - product.sale_price) / product.base_price) * 100
        )
    else:
        product.discount_percentage = None
    product.tag_list = product.tags.split(', ') if product.tags else []
    return product


def _get_user_order(request):
    """Get or create a single pending order for authenticated user (no items)."""
    if request.user.is_authenticated:
        order = Order.objects.filter(
            user=request.user,
            order_status='pending'
        ).order_by('-created_at').first()
        if not order:
            order = Order.objects.create(
                user=request.user,
                order_status='pending',
                subtotal=Decimal('0.00'),
                total=Decimal('0.00')
            )
        return order
    return None


def _get_session_cart(request):
    """Get cart items from session for anonymous users."""
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

def add_to_cart(request, slug):
    """Add product to cart (session for guests; fallback for auth)."""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    if not product.is_in_stock:
        return JsonResponse({'success': False, 'message': f"{product.products_name} is out of stock."}, status=400)

    color = request.POST.get('color')
    size = request.POST.get('size')
    weight = request.POST.get('weight')
    quantity = int(request.POST.get('quantity', 1))

    # --- Unified Session Cart Logic ---
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
    
    # Calculate the total count from the session cart
    cart_count = sum(item['quantity'] for item in cart.values())
    
    # --- Response Logic ---
    if request.user.is_authenticated:
        # NOTE: This still uses the session for counting until a DB cart is implemented.
        messages.success(request, f"{product.products_name} noted for cart (DB add coming soon).")
        response_data = {
            'success': True,
            'message': f"{product.products_name} added (temp)!",
        }
    else:
        response_data = {
            'success': True,
            'message': f"{product.products_name} added to cart!",
        }
        
    # Unified response data
    response_data.update({
        'cart_count': cart_count,
        'product_name': product.products_name,
        'product_image': product.products_image.url if product.products_image else None,
        'quantity': quantity,
        'subtotal': str((product.sale_price or product.current_price) * quantity),
        'checkout_url': reverse('orders:checkout')
    })

    return JsonResponse(response_data)


def view_cart(request):
    """Display cart details for both authenticated and guest users (no OrderItem)."""
    cart_items = []
    subtotal = Decimal('0.00')
    order = None

    if request.user.is_authenticated:
        # Logged-in: No items, just show empty cart message
        order = _get_user_order(request)
        messages.info(request, "Your cart is empty. Add items via the shop.")
    else:
        # Guest: Session-based
        cart_items, subtotal = _get_session_cart(request)

    # Common totals
    shipping_cost = Decimal('0') if subtotal >= Decimal('1000') else Decimal('50')
    tax_amount = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
    total = (subtotal + tax_amount + shipping_cost).quantize(Decimal('0.01'))
    cart_count = len(cart_items)

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


def update_cart(request):
    """Update cart item quantity (session for guests; fallback for auth)."""
    action = request.POST.get('action')
    slug = request.POST.get('slug')
    color = request.POST.get('color', '')
    size = request.POST.get('size', '')
    weight = request.POST.get('weight', '')

    if request.user.is_authenticated:
        messages.error(request, "Cart update not supported for logged-in users yet.")
        return redirect('orders:view_cart')
    else:
        # Guest: Update session
        cart = request.session.get('cart', {})
        cart_key = f"{slug}_{color}_{size}_{weight}"
        if cart_key not in cart:
            messages.error(request, "Item not found in your cart.")
            return redirect('orders:view_cart')

        if action == 'increase':
            cart[cart_key]['quantity'] += 1
        elif action == 'decrease' and cart[cart_key]['quantity'] > 1:
            cart[cart_key]['quantity'] -= 1
        elif action == 'remove':
            cart.pop(cart_key, None)
            messages.success(request, "Item removed from cart!")
            request.session['cart'] = cart
            request.session.modified = True
            return redirect('orders:view_cart')

        request.session['cart'] = cart
        request.session.modified = True
        messages.success(request, "Cart updated successfully!")

    return redirect('orders:view_cart')


def remove_from_cart(request):
    """Remove item from cart (session for guests; fallback for auth)."""
    slug = request.POST.get('slug')  # Use slug for guests

    if request.user.is_authenticated:
        messages.error(request, "Remove not supported for logged-in users yet.")
    else:
        cart = request.session.get('cart', {})
        cart_key = slug  # Assume key is slug-based
        if cart_key in cart:
            cart.pop(cart_key, None)
            request.session['cart'] = cart
            request.session.modified = True
            messages.success(request, "Item removed from cart!")
        else:
            messages.error(request, "Item not found in your cart.")

    return redirect('orders:view_cart')


def checkout(request):
    """Checkout process (session for guests; basic order for auth)."""
    if request.user.is_authenticated:
        order = _get_user_order(request)
        if not order:
            messages.error(request, "Your cart is empty!")
            return redirect('orders:view_cart')
        subtotal = order.subtotal
    else:
        cart_items, subtotal = _get_session_cart(request)
        if not cart_items:
            messages.error(request, "Your cart is empty!")
            return redirect('orders:view_cart')

    # GET: Show form
    if request.method == 'GET':
        shipping_cost = Decimal('0') if subtotal >= Decimal('1000') else Decimal('50')
        tax_amount = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
        total = (subtotal + tax_amount + shipping_cost).quantize(Decimal('0.01'))

        context = {
            'order': order if request.user.is_authenticated else None,
            'subtotal': subtotal,
            'tax_amount': tax_amount,
            'shipping_cost': shipping_cost,
            'total': total,
            'is_guest': not request.user.is_authenticated,
            'cart_items': cart_items if not request.user.is_authenticated else []
        }
        return render(request, 'orders/checkout.html', context)

    # POST: Process
    try:
        if request.user.is_authenticated:
            order.customer_name = request.POST.get('customer_name', order.user.get_full_name())
            # ... (other fields as before)
            order.subtotal = subtotal
            order.total = (subtotal + Decimal(request.POST.get('tax_amount', '0')) + Decimal(request.POST.get('shipping_cost', '0')) - Decimal(request.POST.get('discount_amount', '0')))
            order.order_status = 'processed'
            order.payment_status = 'pending'
            order.save()
        else:
            # Create guest order (no items)
            order = Order.objects.create(
                order_status='processed',
                payment_status='pending',
                customer_name=request.POST.get('customer_name', 'Guest'),
                phone_number=request.POST.get('phone_number'),
                email=request.POST.get('email'),
                shipping_address=request.POST.get('shipping_address'),
                subtotal=subtotal,
                total=subtotal,  # Add tax/shipping as needed
                order_note=request.POST.get('order_note')
            )
            request.session.pop('cart', None)

        messages.success(request, f"Order #{order.id} placed successfully!")
        return redirect('orders:thank_you', order_id=order.id)
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('orders:checkout')


@login_required
def add_review(request):
    """Handle adding a product review (unchanged)."""
    if request.method == 'POST':
        product_slug = request.POST.get('product_slug')
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '')
        title = request.POST.get('title', '')

        product = get_object_or_404(Product, slug=product_slug)
        review, created = Review.objects.get_or_create(
            product=product,
            user=request.user,
            defaults={'rating': rating, 'comment': comment, 'title': title}
        )
        if not created:
            review.rating = rating
            review.comment = comment
            review.title = title
            review.is_approved = False
            review.save()

        messages.success(request, "Your review has been submitted!")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    return redirect('/')


def cart_dropdown_content(request):
    """Return cart content for dropdown (session or empty)."""
    cart_items, cart_total = _get_session_cart(request) if not request.user.is_authenticated else ([], Decimal('0.00'))
    context = {
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    return render(request, 'includes/cart_dropdown_content.html', context)


@login_required
def order_history(request):
    """Display order history for logged-in users."""
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(orders, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'orders': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'orders/order_history.html', context)


@login_required
def order_detail(request, order_id):
    """Display detailed view of a specific order (no items)."""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    context = {'order': order}
    return render(request, 'orders/order_detail.html', context)


def thank_you(request, order_id):
    """Display thank you page."""
    order = get_object_or_404(Order, id=order_id)
    if not request.user.is_authenticated and request.session.get('guest_order_id') != order_id:
        messages.error(request, "Access denied.")
        return redirect('/')
    
    context = {
        'order': order,
        'is_guest': not request.user.is_authenticated,
    }
    return render(request, 'orders/thank_you.html', context)