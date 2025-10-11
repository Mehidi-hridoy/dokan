from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from products.models import Product
from store.models import Category, Brand
from orders.models import Order, OrderItem
from django.db.models import Q
from decimal import Decimal
from django.db import transaction  # ADD THIS IMPORT
from django.utils import timezone  # ADD THIS IMPORT

def _calculate_discount(product):
    """Helper function to calculate discount percentage and tag list"""
    if product.previous_price and product.previous_price > product.price:
        product.discount_percentage = round(
            ((product.previous_price - product.price) / product.previous_price) * 100
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
    for slug, details in cart.items():
        try:
            product = Product.objects.get(slug=slug, is_active=True)
            if product.is_in_stock:
                item_total = product.price * details['quantity']
                cart_items.append({
                    'product': product,
                    'quantity': details['quantity'],
                    'color': details.get('color'),
                    'size': details.get('size'),
                    'weight': details.get('weight'),
                    'total': item_total
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

def home(request):
    products = Product.objects.filter(is_active=True).select_related('category', 'brand')
    categories = Category.objects.all()
    brands = Brand.objects.all()
    
    products = [_calculate_discount(product) for product in products]
    
    # Get cart items for anonymous users
    cart_items, cart_total = _get_session_cart(request) if not request.user.is_authenticated else ([], 0)
    
    context = {
        'products': products,
        'categories': categories,
        'brands': brands,
        'order': _get_user_order(request),
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
        products = products.order_by('name')

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

@require_POST
def add_to_cart(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    if not product.is_in_stock:
        return JsonResponse({'success': False, 'message': f"{product.name} is out of stock."}, status=400)

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
            color=color,
            size=size,
            weight=weight,
            defaults={'quantity': quantity, 'price': product.price}
        )
        if not created:
            order_item.quantity += quantity
            order_item.save()
        
        _calculate_order_total(order)
        
        return JsonResponse({
            'success': True,
            'message': f"{product.name} added to cart!",
            'cart_count': order.order_items.count()
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
        
        return JsonResponse({
            'success': True,
            'message': f"{product.name} added to cart!",
            'cart_count': len(cart)
        })

def _calculate_order_total(order):
    """Helper function to calculate order total"""
    total = sum(item.get_total() for item in order.order_items.all())
    order.total = total
    order.save()
    return order

@login_required
def view_cart(request):
    order = _get_user_order(request)
    cart_items, cart_total = _get_session_cart(request) if not request.user.is_authenticated else ([], 0)
    
    context = {
        'order': order,
        'order_items': order.order_items.select_related('product').all() if order else [],
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    return render(request, 'orders/cart.html', context)

@login_required
def checkout(request):
    """Checkout process for authenticated users"""
    order = _get_user_order(request)
    
    # Check if order exists and has items
    if not order or not hasattr(order, 'items') or not order.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('products:view_cart')  # FIXED: Use namespace
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Update order with customer information
                order.customer_name = request.POST.get('customer_name', f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username)
                order.phone_number = request.POST.get('phone_number', '')
                order.email = request.POST.get('email', request.user.email)
                order.shipping_address = request.POST.get('shipping_address', '')
                order.billing_address = request.POST.get('billing_address', '') or request.POST.get('shipping_address', '')
                order.order_note = request.POST.get('order_note', '')
                order.payment_method = request.POST.get('payment_method', 'cash_on_delivery')
                order.delivery_area = request.POST.get('delivery_area', '')
                order.city = request.POST.get('city', '')
                order.zip_code = request.POST.get('zip_code', '')
                
                # Calculate final totals
                order.tax_amount = float(request.POST.get('tax_amount', 0) or 0)
                order.shipping_cost = float(request.POST.get('shipping_cost', 0) or 0)
                order.discount_amount = float(request.POST.get('discount_amount', 0) or 0)
                
                # Recalculate total
                order.total = order.subtotal + order.tax_amount + order.shipping_cost - order.discount_amount
                
                # Update order status
                order.order_status = 'processed'
                order.payment_status = 'pending'
                
                # For demo, mark as paid if payment method is not COD
                if order.payment_method != 'cash_on_delivery':
                    order.payment_status = 'paid'
                    order.processed_at = timezone.now()
                
                order.save()
                
                messages.success(request, f'Order #{order.order_number} placed successfully!')
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Order #{order.order_number} placed successfully!',
                        'redirect': f'/thank-you/{order.id}/',
                        'order_id': order.id
                    })
                else:
                    return redirect('products:thank_you', order_id=order.id)  # FIXED: Use namespace
                    
        except Exception as e:
            messages.error(request, f'Error processing order: {str(e)}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
            else:
                return redirect('products:checkout')  # FIXED: Use namespace
    
    # Calculate shipping and tax
    shipping_cost = 0 if order.subtotal >= 500 else 50  # Free shipping above ₹500
    tax_amount = order.subtotal * 0.18  # 18% GST
    
    context = {
        'order': order,
        'subtotal': order.subtotal,
        'tax_amount': tax_amount,
        'shipping_cost': shipping_cost,
        'total': order.subtotal + tax_amount + shipping_cost,
    }
    return render(request, 'orders/checkout.html', context)

@login_required
def thank_you(request, order_id):
    """Order thank you page"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.select_related('product').all()
    
    context = {
        'order': order,
        'order_items': order_items,
    }
    return render(request, 'orders/thank_you.html', context)

# Make sure _get_user_order function exists
def _get_user_order(request):
    """Get or create a single pending order for authenticated user"""
    if request.user.is_authenticated:
        try:
            # Try to get the most recent pending order
            order = Order.objects.filter(
                user=request.user,
                order_status='pending'
            ).latest('created_at')
        except Order.DoesNotExist:
            # Create a new pending order
            order = Order.objects.create(
                user=request.user,
                order_status='pending'
            )
        except Order.MultipleObjectsReturned:
            # Handle multiple orders by getting the most recent and cleaning up others
            orders = Order.objects.filter(
                user=request.user,
                order_status='pending'
            ).order_by('-created_at')
            order = orders.first()
            # Delete the older duplicate orders
            orders.exclude(id=order.id).delete()
        
        return order
    return None


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
    return render(request, 'orders/order_history.html', context)