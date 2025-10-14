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
from . models import Review
from orders.views import _get_session_cart, _calculate_discount, _get_user_order


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
