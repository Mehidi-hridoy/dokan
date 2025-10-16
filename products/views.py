# products/views.py
from decimal import Decimal
from typing import List, Tuple, Dict, Any

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView

from products.models import Product, Review
from store.models import Category, Brand
from decimal import Decimal


# ----------------------------------------------------------------------
# Helper functions (replace with the real implementations from orders app)
# ----------------------------------------------------------------------
def _calculate_discount(product: Product) -> Product:
    """
    Placeholder – apply any active discount logic here.
    For the moment it simply adds a ``discounted_price`` attribute.
    """
    # Example: 10% off if a sale_price exists
    if product.sale_price and product.sale_price < product.base_price:
        product.discounted_price = product.sale_price
    else:
        product.discounted_price = product.base_price
    return product


def _get_session_cart(request) -> Tuple[List[Dict[str, Any]], Decimal]:
    """
    Return cart items and total for anonymous users.
    Replace with your real session-based cart logic.
    """
    cart = request.session.get('cart', {})
    items = []
    total = Decimal('0.00')
    # dummy implementation – adapt to your session format
    return items, total


def _get_user_order(request):
    """
    Return the **open** Order object for the logged-in user (or None).
    Replace with the real implementation from orders.views.
    """
    # Example stub:
    # from orders.models import Order
    # return Order.objects.filter(user=request.user, status='cart').first()
    return None


# products/views.py (The fixed home function)

def home(request):
    """
    Home page – shows active products, categories, brands and the current cart.
    """
    from decimal import Decimal
    
    # 🌟 FIX: Use the correct related_name 'inventory_reverse' for select_related
    products_qs = Product.objects.filter(is_active=True).select_related(
        'category', 
        'brand',
        'inventory_reverse' # <-- CRITICAL CHANGE HERE to match the related_name on Inventory
    )
    
    products = [_calculate_discount(p) for p in products_qs]

    categories = Category.objects.all()
    brands = Brand.objects.all()

    # ---------- cart handling ----------
    if request.user.is_authenticated:
        order = _get_user_order(request)
        cart_items, cart_total = [], Decimal('0.00')
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


# products/views.py
class ProductListView(ListView):
    model = Product
    template_name = 'products/list.html'
    context_object_name = 'products'
    paginate_by = 10  # 10 products per page

    def get_queryset(self):
        queryset = Product.objects.select_related('inventory').prefetch_related('images', 'reviews').all()
        
        # Search by name/description
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(Q(products_name__icontains=search) | Q(description__icontains=search))
        
        # Filter by price range
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            queryset = queryset.filter(current_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(current_price__lte=max_price)
        
        # Sort
        sort = self.request.GET.get('sort', 'name_asc')
        if sort == 'price_asc':
            queryset = queryset.order_by('current_price')
        elif sort == 'price_desc':
            queryset = queryset.order_by('-current_price')
        elif sort == 'name_asc':
            queryset = queryset.order_by('products_name')
        elif sort == 'rating_desc':
            queryset = queryset.annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add avg rating and stock to each product (annotate for efficiency)
        for product in context['products']:
            product.avg_rating = product.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
            product.stock_available = product.inventory.available_quantity if product.inventory else 0
            product.is_out_of_stock = product.stock_available <= 0
            product.thumbnail = product.images.first().image.url if product.images.exists() else '/static/default.jpg'
        return context

class ProductDetailView(DetailView):
    model = Product
    template_name = 'products/detail.html'
    context_object_name = 'product'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reviews'] = self.object.reviews.all()
        context['avg_rating'] = self.object.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        context['stock_available'] = self.object.inventory.available_quantity if self.object.inventory else 0
        return context

def product_detail(request, slug):
    """
    Product detail page – also shows reviews and cart summary.
    """
    product = get_object_or_404(Product, slug=slug, is_active=True)
    product = _calculate_discount(product)

    # Cart for anonymous users only (authenticated users get order only)
    if request.user.is_authenticated:
        cart_items, cart_total = [], Decimal('0.00')
        order = _get_user_order(request)
    else:
        order = None
        cart_items, cart_total = _get_session_cart(request)

    context = {
        'product': product,
        'reviews': product.reviews.filter(is_approved=True).select_related('user'),
        'order': order,
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    return render(request, 'products/product_detail.html', context)


def search(request):
    """
    Simple search by product name or description.
    """
    query = request.GET.get('q', '').strip()
    products_qs = Product.objects.filter(is_active=True).select_related('category', 'brand')

    if query:
        products_qs = products_qs.filter(
            Q(products_name__icontains=query) |
            Q(description__icontains=query)
        )

    products = [_calculate_discount(p) for p in products_qs]

    # Cart handling (same logic as home page)
    if request.user.is_authenticated:
        order = _get_user_order(request)
        cart_items, cart_total = [], Decimal('0.00')  # No OrderItem, so empty
    else:
        order = None
        cart_items, cart_total = _get_session_cart(request)

    context = {
        'products': products,
        'categories': Category.objects.all(),
        'brands': Brand.objects.all(),
        'query': query,
        'order': order,
        'cart_items': cart_items,
        'cart_total': cart_total,
    }
    return render(request, 'products/search_results.html', context)


def search_suggestions(request):
    """
    AJAX endpoint that powers the live-search dropdown.
    Returns up to 5 matching products (name, slug, price, image).
    """
    query = request.GET.get('q', '').strip()
    products_qs = Product.objects.filter(is_active=True)

    if query:
        products_qs = products_qs.filter(
            Q(products_name__icontains=query) |
            Q(description__icontains=query)
        )[:5]

    suggestions = []
    for p in products_qs:
        suggestions.append({
            'name': p.products_name,
            'slug': p.slug,
            'price': str(p.sale_price or p.base_price),
            'image': p.products_image.url if p.products_image else None,
        })

    return JsonResponse({'products': suggestions})