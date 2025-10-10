from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from products.models import Product
from store.models import Category, Brand
from orders.models import Order, OrderItem
from django.db.models import Q

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
    """Helper function to get current user's active order"""
    if request.user.is_authenticated:
        # Get orders that are not completed (pending, processing, etc.)
        # Adjust the status values based on your actual order status choices
        active_statuses = ['pending', 'processing', 'on_hold']  # Add your actual status values
        return Order.objects.filter(
            user=request.user, 
            order_status__in=active_statuses
        ).first()
    return None
 
def home(request):
    products = Product.objects.filter(is_active=True).select_related('category', 'brand')
    categories = Category.objects.all()
    brands = Brand.objects.all()
    
    products = [_calculate_discount(product) for product in products]
    
    context = {
        'products': products,
        'categories': categories,
        'brands': brands,
        'order': _get_user_order(request),
    }
    return render(request, 'products/home.html', context)


def product_list(request):
    category_slug = request.GET.get('category', '')
    brand_slug = request.GET.get('brand', '')
    tag = request.GET.get('tag', '')
    sort = request.GET.get('sort', 'name')

    # Start with all active products
    products = Product.objects.filter(is_active=True).select_related('category', 'brand')
    categories = Category.objects.all()
    brands = Brand.objects.all()

    # Apply filters
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
        header_name = category.name
        # Get brands that have products in this category
        brands = brands.filter(products__category=category, products__is_active=True).distinct()
    elif brand_slug:
        brand = get_object_or_404(Brand, slug=brand_slug)
        products = products.filter(brand=brand)
        header_name = brand.name
        # Get categories that have products from this brand
        categories = categories.filter(products__brand=brand, products__is_active=True).distinct()
    elif tag:
        products = products.filter(tags__icontains=tag)
        header_name = f"Products tagged with: {tag}"
    else:
        header_name = "All Products"

    # Apply sorting
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    elif sort == 'name':
        products = products.order_by('name')

    # Get product counts for categories and brands in the current filtered view
    category_counts = {}
    for category in categories:
        count = Product.objects.filter(category=category, is_active=True).count()
        category_counts[category.id] = count
    
    brand_counts = {}
    for brand in brands:
        count = Product.objects.filter(brand=brand, is_active=True).count()
        brand_counts[brand.id] = count

    # Check if user can review each product
    if request.user.is_authenticated:
        # Get delivered orders for the current user
        delivered_orders = Order.objects.filter(
            user=request.user,
            order_status='delivered'
        )
        
        # Get product IDs that user has received
        delivered_product_ids = OrderItem.objects.filter(
            order__in=delivered_orders
        ).values_list('product_id', flat=True).distinct()
        
        # Check for each product if user can review
        for product in products:
            product.can_review = product.id in delivered_product_ids and not product.reviews.filter(user=request.user).exists()
    else:
        for product in products:
            product.can_review = False

    products = [_calculate_discount(product) for product in products]

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
    }
    return render(request, 'products/product_list.html', context)


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    product = _calculate_discount(product)
    
    context = {
        'product': product,
        'reviews': product.reviews.all(),
        'order': _get_user_order(request),
    }
    return render(request, 'products/product_detail.html', context)

def search(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(is_active=True).select_related('category', 'brand')
    
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    
    products = [_calculate_discount(product) for product in products]
    
    context = {
        'products': products,
        'categories': Category.objects.all(),
        'brands': Brand.objects.all(),
        'query': query,
        'order': _get_user_order(request),
    }
    return render(request, 'products/search_results.html', context)

@require_POST
@login_required
def add_to_cart(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    if not product.is_in_stock:
        return JsonResponse({'success': False, 'message': f"{product.name} is out of stock."}, status=400)

    # Get or create an order with pending status
    order = Order.objects.filter(user=request.user, order_status='pending').first()
    
    if not order:
        order = Order.objects.create(
            user=request.user,
            order_status='pending',
            total=0
        )

    order_item, created = OrderItem.objects.get_or_create(
        order=order,
        product=product,
        color=request.POST.get('color'),
        size=request.POST.get('size'),
        weight=request.POST.get('weight'),
        defaults={'quantity': 1, 'price': product.price}
    )

    if not created:
        order_item.quantity += 1
        order_item.save()

    # Recalculate order total
    _calculate_order_total(order)
    
    return JsonResponse({
        'success': True,
        'message': f"{product.name} added to cart!",
        'cart_count': order.order_items.count()
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
    context = {
        'order': order,
        'order_items': order.order_items.select_related('product').all() if order else [],
    }
    return render(request, 'orders/cart.html', context)

@require_POST
@login_required
def checkout(request):
    order = _get_user_order(request)
    if not order or not order.order_items.exists():
        return JsonResponse({'success': False, 'message': "Your cart is empty."}, status=400)

    shipping_address = request.POST.get('address')
    phone_number = request.POST.get('phone_number')
    payment_method = request.POST.get('payment_method')

    if not all([shipping_address, phone_number, payment_method]):
        return JsonResponse({'success': False, 'message': "Missing required fields."}, status=400)

    # Update order with checkout information and mark as completed
    order.shipping_address = shipping_address
    order.phone_number = phone_number
    order.payment_method = payment_method
    order.order_status = 'completed'  # Use your actual completed status value
    order.save()

    return JsonResponse({'success': True, 'message': "Order placed successfully!", 'redirect': '/orders/history/'})

@login_required
def order_history(request):
    # Get completed orders - adjust the status based on your actual completed status
    completed_statuses = ['completed', 'delivered']  # Add your actual completed status values
    orders = Order.objects.filter(
        user=request.user, 
        order_status__in=completed_statuses
    ).select_related('user').order_by('-created_at')
    return render(request, 'products/order_history.html', {'orders': orders})