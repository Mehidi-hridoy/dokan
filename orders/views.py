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
from products.views import calculate_discount
from django.http import JsonResponse
from .models import Order, OrderItem
from analytics.models import Customer

def _get_user_order(request):
    """Get or create a single pending order for authenticated user (no items)."""
    if request.user.is_authenticated:
        order = Order.objects.filter(
            user=request.user,
            order_status='pending'
        ).order_by('-created_at').first()
        if not order:
            customer, _ = Customer.objects.get_or_create(
                user=request.user,
                defaults={'name': request.user.get_full_name() or request.user.username, 'email': request.user.email}
            )
            order = Order.objects.create(
                user=request.user,
                customer=customer,
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
                    'cart_key': key,
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


def thank_you(request, order_id):
    """Display thank you page after order placement."""
    order = get_object_or_404(Order, id=order_id)

    # Restrict access
    if request.user.is_authenticated:
        if order.user != request.user:
            messages.error(request, "Access denied.")
            return redirect('products:home')
    else:
        if request.session.get('guest_order_id') != order_id:
            messages.error(request, "Access denied.")
            return redirect('products:home')

    context = {
        'order': order,
        'is_guest': not request.user.is_authenticated,
    }
    return render(request, 'orders/thank_you.html', context)


def checkout(request):
    """Handle checkout form submission and create/update an order."""
    if request.user.is_authenticated:
        order = _get_user_order(request)
        cart_items, cart_total = _get_session_cart(request)
    else:
        cart_items, cart_total = _get_session_cart(request)
        order = None

    if not cart_items:
        messages.error(request, "Your cart is empty.")
        return redirect('products:product_list')

    if request.method == 'POST':
        shipping_address = request.POST.get('shipping_address')
        email = request.POST.get('email') if not request.user.is_authenticated else None
        phone_number = request.POST.get('phone_number') if not request.user.is_authenticated else None
        customer_name = request.POST.get('customer_name') if not request.user.is_authenticated else None

        # Validate inputs
        if not shipping_address:
            messages.error(request, "Shipping address is required.")
            return render(request, 'orders/checkout.html', {
                'cart_items': cart_items,
                'cart_total': cart_total,
                'cart_count': sum(item['quantity'] for item in cart_items),
            })

        if not request.user.is_authenticated and not (email and customer_name):
            messages.error(request, "Name and email are required for guest checkout.")
            return render(request, 'orders/checkout.html', {
                'cart_items': cart_items,
                'cart_total': cart_total,
                'cart_count': sum(item['quantity'] for item in cart_items),
            })

        # Create or update order
        if request.user.is_authenticated:
            order.subtotal = cart_total
            order.total = cart_total  # Add tax/shipping/discount if needed
            order.shipping_address = shipping_address
            order.save()
        else:
            customer, _ = Customer.objects.get_or_create(
                email=email,
                defaults={'name': customer_name, 'phone': phone_number}
            )
            order = Order.objects.create(
                user=None,
                customer=customer,
                order_status='pending',
                subtotal=cart_total,
                total=cart_total,
                shipping_address=shipping_address,
                customer_name=customer_name,
                email=email,
                phone_number=phone_number
            )

        # Clear existing items for authenticated users
        if request.user.is_authenticated:
            order.items.all().delete()

        # Create order items
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                quantity=item['quantity']
            )

        # Clear session cart
        request.session['cart'] = {}
        request.session.modified = True

        # Store guest order ID
        if not request.user.is_authenticated:
            request.session['guest_order_id'] = order.id
            request.session.modified = True

        messages.success(request, f"Order {order.order_number} placed successfully!")
        return redirect('orders:thank_you', order_id=order.id)

    return render(request, 'orders/checkout.html', {
        'cart_items': cart_items,
        'cart_total': cart_total,
        'cart_count': sum(item['quantity'] for item in cart_items),
    })

# orders/views.py
def checkout_from_product(request, product_slug):
    if request.method == 'POST':
        product = get_object_or_404(Product, slug=product_slug)
        quantity = int(request.POST.get('quantity', 1))
        color = request.POST.get('color', '')
        size = request.POST.get('size', '')
        weight = request.POST.get('weight', 'default')

        # Add to cart logic (same as add_to_cart)
        if request.user.is_authenticated:
            order, created = Order.objects.get_or_create(user=request.user, status='cart')
            order_item, created = OrderItem.objects.get_or_create(
                order=order,
                product=product,
                color=color,
                size=size,
                defaults={'quantity': quantity, 'weight': weight}
            )
            if not created:
                order_item.quantity += quantity
                order_item.save()
            cart_items = order.orderitem_set.count()
            cart_total = order.get_total()
        else:
            cart = request.session.get('cart', {})
            product_key = f"{product.id}_{color}_{size}_{weight}"
            if product_key in cart:
                cart[product_key]['quantity'] += quantity
            else:
                cart[product_key] = {'quantity': quantity, 'color': color, 'size': size, 'weight': weight}
            request.session['cart'] = cart
            cart_items = sum(item['quantity'] for item in cart.values())
            cart_total = sum(
                Decimal(item['quantity']) * product.sale_price
                for item in cart.values()
            )

        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Added to cart, redirecting to checkout...',
                'cart_count': cart_items,
                'cart_total': str(cart_total),
            })
        else:
            messages.success(request, 'Product added to cart!')
            return redirect('orders:checkout')
    
    return redirect('products:product_list')

def add_to_cart(request, slug):
    """Add product to cart (session-based for now)."""
    product = get_object_or_404(Product, slug=slug, is_active=True)

    # Get selected options from POST
    color = request.POST.get('color')
    size = request.POST.get('size')
    weight = request.POST.get('weight')
    quantity = int(request.POST.get('quantity', 1))

    # --- VALIDATION SECTION ---

    # Check stock
    if not product.is_in_stock:
        return JsonResponse({'success': False, 'message': f"{product.products_name} is out of stock."}, status=400)

    # Make sure color and size are selected if product has those options
    if product.color and not color:
        messages.error(request, "Please select a color before adding to cart.")
        return redirect('products:product_detail', slug=product.slug)

    if product.size and not size:
        messages.error(request, "Please select a size before adding to cart.")
        return redirect('products:product_detail', slug=product.slug)

    # --- CART LOGIC ---
    cart = request.session.get('cart', {})
    cart_key = f"{slug}_{color or 'default'}_{size or 'default'}_{weight or 'default'}"

    if cart_key in cart:
        cart[cart_key]['quantity'] += quantity
    else:
        cart[cart_key] = {
            'slug': slug,
            'quantity': quantity,
            'color': color,
            'size': size,
            'weight': weight,
        }

    request.session['cart'] = cart
    request.session.modified = True

    # Calculate total cart count
    cart_count = sum(item['quantity'] for item in cart.values())

    # Determine correct product price
    product_price = product.sale_price or getattr(product, 'current_price', product.base_price)

    # Response payload
    response_data = {
        'success': True,
        'message': f"{product.products_name} added to your cart!",
        'cart_count': cart_count,
        'product_name': product.products_name,
        'product_image': product.products_image.url if product.products_image else None,
        'quantity': quantity,
        'subtotal': str(product_price * quantity),
        'checkout_url': reverse('orders:checkout'),
    }

    messages.success(request, f"{product.products_name} added to cart successfully.")
    return JsonResponse(response_data)



def view_cart(request):
    """Render the cart view with session-based cart items."""
    cart = request.session.get('cart', {})
    cart_items = []
    total_price = 0

    for cart_key, item in cart.items():
        try:
            product = get_object_or_404(Product, slug=item['slug'], is_active=True)
            subtotal = (product.sale_price or product.current_price) * item['quantity']
            total_price += subtotal
            cart_items.append({
                'cart_key': cart_key,
                'product': product,
                'quantity': item['quantity'],
                'color': item['color'],
                'size': item['size'],
                'weight': item['weight'],
                'subtotal': subtotal,
            })
        except Http404:
            # Remove invalid product from cart
            del cart[cart_key]
            request.session['cart'] = cart
            request.session.modified = True

    context = {
        'cart_items': cart_items,
        'total_price': total_price,
        'cart_count': sum(item['quantity'] for item in cart.values()),
        'checkout_url': reverse('orders:checkout')
    }

    return render(request, 'orders/cart.html', context)

def update_cart(request):
    """Update quantity of a cart item."""
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        cart_key = request.POST.get('cart_key')
        quantity = int(request.POST.get('quantity', 1))

        if cart_key in cart and quantity > 0:
            cart[cart_key]['quantity'] = quantity
            request.session['cart'] = cart
            request.session.modified = True
            product = get_object_or_404(Product, slug=cart[cart_key]['slug'], is_active=True)
            messages.success(request, f"Updated {product.products_name} quantity to {quantity}.")
        elif cart_key in cart and quantity == 0:
            del cart[cart_key]
            request.session['cart'] = cart
            request.session.modified = True
            messages.success(request, "Item removed from cart.")
        else:
            messages.error(request, "Invalid cart item or quantity.")

    return redirect('orders:view_cart')


def remove_from_cart(request):
    """Remove an item from the cart."""
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        cart_key = request.POST.get('cart_key')

        if cart_key in cart:
            product = get_object_or_404(Product, slug=cart[cart_key]['slug'], is_active=True)
            del cart[cart_key]
            request.session['cart'] = cart
            request.session.modified = True
            cart_count = sum(item['quantity'] for item in cart.values())
            response_data = {
                'success': True,
                'message': f"{product.products_name} removed from cart.",
                'cart_count': cart_count
            }
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(response_data)
            messages.success(request, f"{product.products_name} removed from cart.")
        else:
            response_data = {
                'success': False,
                'message': "Item not found in cart."
            }
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(response_data, status=400)
            messages.error(request, "Item not found in cart.")

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'message': "Invalid request."}, status=400)
    return redirect('orders:view_cart')

# Ensure other views (add_to_cart, cart_dropdown_content, etc.) remain as provided
def cart_dropdown_content(request):
    """Render the cart dropdown content with session-based cart items."""
    cart = request.session.get('cart', {})
    cart_items = []
    total_price = 0
    cart_count = 0

    for cart_key, item in cart.items():
        try:
            product = get_object_or_404(Product, slug=item['slug'], is_active=True)
            subtotal = (product.sale_price or product.current_price) * item['quantity']
            total_price += subtotal
            cart_count += item['quantity']
            cart_items.append({
                'cart_key': cart_key,
                'product': product,
                'quantity': item['quantity'],
                'color': item['color'],
                'size': item['size'],
                'weight': item['weight'],
                'subtotal': subtotal,
            })
        except Http404:
            del cart[cart_key]
            request.session['cart'] = cart
            request.session.modified = True

    context = {
        'cart_items': cart_items,
        'total_price': total_price,
        'cart_count': cart_count,
        'checkout_url': reverse('orders:checkout')
    }

    return render(request, 'includes/cart_dropdown_content.html', context)


@login_required
def add_review(request):
    if request.method == 'POST':
        product_slug = request.POST.get('product_slug')
        rating = int(request.POST.get('rating', 0))
        title = request.POST.get('title', '')
        comment = request.POST.get('comment', '')

        product = get_object_or_404(Product, slug=product_slug)

        # Save review as not approved
        Review.objects.update_or_create(
            user=request.user,
            product=product,
            defaults={'rating': rating, 'title': title, 'comment': comment, 'is_approved': False}
        )

        messages.success(request, "Review submitted successfully! It will appear once approved.")
        return redirect('products:product_detail', slug=product.slug)


def order_detail(request, order_id):
    """Display detailed view of a specific order with items."""
    # Ensure the order belongs to the logged-in user
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Get all items for this order
    order_items = order.items.select_related('product').all()
    
    context = {
        'order': order,
        'order_items': order_items,
    }
    return render(request, 'orders/order_detail.html', context)



@login_required
def order_history(request):
    """Display paginated order history for logged-in users."""
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    # Prefetch related items for efficiency
    orders = orders.prefetch_related('items__product')
    
    paginator = Paginator(orders, 10)  # 10 orders per page
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'orders': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'orders/order_history.html', context)
