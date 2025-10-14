from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from products.models import Product
from store.models import Category, Brand
from orders.models import Order, OrderItem
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from decimal import Decimal  # ✅ Keep only this one
from .models import Product
from django.urls import reverse


def home(request):
    products = Product.objects.filter(is_active=True).select_related('category', 'brand')
    categories = Category.objects.all()
    brands = Brand.objects.all()
    
    products = [_calculate_discount(product) for product in products]
    
    # Get cart items for both authenticated and anonymous users
    if request.user.is_authenticated:
        order = _get_user_order(request)
        cart_items = []
        cart_total = Decimal('0.00')
    else:
        order = None
        cart_items, cart_total = _get_session_cart(request)
    
    context = {
        'products': products,
        'categories': categories,
        'brands': brands,
        'order': order,
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    return render(request, 'products/home.html', context)

def product_list(request):
    category_slug = request.GET.get('category', '')
    brand_slug = request.GET.get('brand', '')
    tag = request.GET.get('tag', '')
    sort = request.GET.get('sort', 'name')

    products = Product.objects.filter(is_active=True).select_related('category', 'brand')
    categories = Category.objects.all()
    brands = Brand.objects.all()

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(Q(category=category) | Q(sub_category=category))
        header_name = category.name
        brands = brands.filter(products__category=category, products__is_active=True).distinct()
    elif brand_slug:
        brand = get_object_or_404(Brand, slug=brand_slug)
        products = products.filter(brand=brand)
        header_name = brand.name
        categories = categories.filter(products__brand=brand, products__is_active=True).distinct()
    elif tag:
        products = products.filter(tags__icontains=tag)
        header_name = f"Products tagged with: {tag}"
    else:
        header_name = "All Products"

    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    elif sort == 'name':
        products = products.order_by('-products_name')

    category_counts = {category.id: Product.objects.filter(category=category, is_active=True).count() for category in categories}
    brand_counts = {brand.id: Product.objects.filter(brand=brand, is_active=True).count() for brand in brands}

    if request.user.is_authenticated:
        delivered_orders = Order.objects.filter(user=request.user, order_status='delivered')
        delivered_product_ids = OrderItem.objects.filter(order__in=delivered_orders).values_list('product_id', flat=True).distinct()
        for product in products:
            product.can_review = product.id in delivered_product_ids and not product.reviews.filter(user=request.user).exists()
    else:
        for product in products:
            product.can_review = False

    products = [_calculate_discount(product) for product in products]
    
    cart_items, cart_total = _get_session_cart(request) if not request.user.is_authenticated else ([], 0)

    context = {
        'products': products,
        'categories': categories,
        'brands': brands,
        'category_counts': category_counts,
        'brand_counts': brand_counts,
        'header_name': header_name,
        'selected_category': category_slug,
        'selected_brand': brand_slug,
        'selected_tag': tag,
        'current_sort': sort,
        'order': _get_user_order(request),
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    return render(request, 'products/product_list.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    product = _calculate_discount(product)
    
    cart_items, cart_total = _get_session_cart(request) if not request.user.is_authenticated else ([], 0)
    
    context = {
        'product': product,
        'reviews': product.reviews.all(),
        'order': _get_user_order(request),
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    return render(request, 'products/product_detail.html', context)

def search(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(is_active=True).select_related('category', 'brand')
    
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    
    products = [_calculate_discount(product) for product in products]
    
    cart_items, cart_total = _get_session_cart(request) if not request.user.is_authenticated else ([], 0)
    
    context = {
        'products': products,
        'categories': Category.objects.all(),
        'brands': Brand.objects.all(),
        'query': query,
        'order': _get_user_order(request),
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    return render(request, 'products/search_results.html', context)

# Add this to your views.py
def search_suggestions(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(is_active=True)
    
    if query:
        products = products.filter(
            Q(products_name__icontains=query) | 
            Q(description__icontains=query)
        )[:5]  # Limit to 5 results
    
    suggestions = []
    for product in products:
        suggestions.append({
            'name': product.products_name,
            'slug': product.slug,
            'price': str(product.sale_price or product.current_price),
            'image': product.products_image.url if product.products_image else None,
        })
    
    return JsonResponse({'products': suggestions})

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


def view_cart(request):
    """
    Display the cart for both logged-in users and guests.
    """
    if request.user.is_authenticated:
        # Logged-in user
        order = _get_user_order(request)
        order_items = order.order_items.select_related('product').all() if order else []
        cart_count = order.order_items.count() if order else 0
        subtotal = sum(item.get_total() for item in order_items) if order else Decimal('0')
    else:
        # Guest user
        order = None
        cart_items, cart_total = _get_session_cart(request)
        order_items = []
        for cart_item in cart_items:
            order_items.append({
                'product': cart_item['product'],
                'quantity': cart_item['quantity'],
                'unit_price': cart_item['product'].sale_price or cart_item['product'].current_price,
                'color': cart_item.get('color'),
                'size': cart_item.get('size'),
                'weight': cart_item.get('weight'),
                'get_total': lambda item=cart_item: item['total'],  # Keep the interface same as logged-in
            })
        cart_count = len(cart_items)
        subtotal = cart_total

    # Shipping and tax calculation
    shipping_cost = Decimal('0') if subtotal >= Decimal('1000') else Decimal('50')
    tax_amount = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
    total = (subtotal + tax_amount + shipping_cost).quantize(Decimal('0.01'))

    context = {
        'order': order,
        'order_items': order_items,
        'cart_count': cart_count,
        'subtotal': subtotal,
        'tax_amount': tax_amount,
        'shipping_cost': shipping_cost,
        'total': total,
        'is_guest': not request.user.is_authenticated,
    }

    return render(request, 'orders/cart.html', context)


def checkout(request):
    """Checkout process for both authenticated and guest users"""
    
    # --- Identify order ---
    if request.user.is_authenticated:
        order = _get_user_order(request)
        if not order or not order.order_items.exists():
            messages.error(request, "Your cart is empty!")
            return redirect('products:view_cart')
    else:
        cart_items, cart_total = _get_session_cart(request)
        if not cart_items:
            messages.error(request, "Your cart is empty!")
            return redirect('products:view_cart')

        # Temporary guest order
        order = Order.objects.create(
            order_status='pending',
            customer_name="",
            total=cart_total
        )
        request.session['guest_order_id'] = order.id

    # --- Handle POST submission ---
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Update customer details
                order.customer_name = request.POST.get(
                    'customer_name',
                    f"{request.user.first_name} {request.user.last_name}".strip()
                    if request.user.is_authenticated else ""
                )
                order.phone_number = request.POST.get('phone_number', '')
                order.email = request.POST.get(
                    'email',
                    request.user.email if request.user.is_authenticated else ""
                )
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

                # Guest users: create order items from session cart
                if not request.user.is_authenticated:
                    for cart_item in cart_items:
                        OrderItem.objects.create(
                            order=order,
                            product=cart_item['product'],
                            quantity=cart_item['quantity'],
                            unit_price=cart_item['product'].sale_price or cart_item['product'].current_price,
                            original_unit_price=cart_item['product'].current_price,
                            color=cart_item.get('color'),
                            size=cart_item.get('size'),
                            weight=cart_item.get('weight')
                        )

                # Financials
                order.tax_amount = Decimal(request.POST.get('tax_amount', '0') or '0')
                order.shipping_cost = Decimal(request.POST.get('shipping_cost', '0') or '0')
                order.discount_amount = Decimal(request.POST.get('discount_amount', '0') or '0')

                # Subtotal from order items
                order.subtotal = sum(
                    (item.unit_price * item.quantity for item in order.order_items.all()),
                    Decimal('0')
                )

                # Total
                order.total = order.subtotal + order.tax_amount + order.shipping_cost - order.discount_amount

                # Order status
                order.order_status = 'processed'
                order.payment_status = 'pending'
                if order.payment_method != 'cash_on_delivery':
                    order.payment_status = 'paid'
                    order.processed_at = timezone.now()

                order.save()

                # Clear guest session data
                if not request.user.is_authenticated:
                    request.session.pop('cart', None)
                    request.session.pop('guest_order_id', None)

                messages.success(request, f'Order #{order.order_number} placed successfully!')

                # AJAX or normal redirect
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Order #{order.order_number} placed successfully!',
                        'redirect': f'/thank-you/{order.id}/',
                        'order_id': order.id
                    })
                return redirect('products:thank_you', order_id=order.id)

        except Exception as e:
            import traceback
            print("🧩 DEBUG TRACEBACK:", traceback.format_exc())
            messages.error(request, f'Error processing order: {str(e)}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(e)})
            return redirect('products:checkout')

    # --- GET: calculate totals ---
    if request.user.is_authenticated:
        subtotal = sum((item.unit_price * item.quantity for item in order.order_items.all()), Decimal('0'))
    else:
        subtotal = cart_total

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
                item_total = (product.sale_price or product.current_price) * details['quantity']
                cart_items.append({
                    'product': product,
                    'quantity': details['quantity'],
                    'color': details.get('color'),
                    'size': details.get('size'),
                    'weight': details.get('weight'),
                    'total': item_total,
                    'unit_price': product.sale_price or product.current_price
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

from .models import Review

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

