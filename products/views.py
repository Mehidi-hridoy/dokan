# products/views.py
from decimal import Decimal
from typing import List, Tuple, Dict, Any
from django.db.models import Count

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q, Avg
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView

from products.models import Product, Review
from store.models import Category, Brand
from decimal import Decimal




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


def home(request):
    """
    Home page – shows active products, categories, brands and the current cart.
    Products in stock will be displayed first.
    """
    
    products_qs = Product.objects.filter(is_active=True).select_related(
        'category', 
        'brand',
        'inventory_reverse'
    )
    
    # Calculate discounts for each product
    products = [_calculate_discount(p) for p in products_qs]

    # Sort: products in stock first, then by created_at descending
    products = sorted(
        products, 
        key=lambda p: (not p.is_in_stock, -p.created_at.timestamp())
    )

    categories = Category.objects.all()
    brands = Brand.objects.all()

    # Cart handling
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


class ProductListView(ListView):
    model = Product
    template_name = 'products_list.html'
    context_object_name = 'products'
    paginate_by = 10

    def get_queryset(self):
        queryset = Product.objects.select_related('inventory', 'category', 'brand')\
                                  .prefetch_related('images', 'reviews')\
                                  .all()

        # Filters
        search = self.request.GET.get('search')
        category_slug = self.request.GET.get('category')
        brand_slug = self.request.GET.get('brand')
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        sort = self.request.GET.get('sort', 'name_asc')

        if search:
            queryset = queryset.filter(
                Q(products_name__icontains=search) | Q(description__icontains=search)
            )
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)
        if min_price:
            queryset = queryset.filter(sale_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(sale_price__lte=max_price)

        # Annotate avg_rating for all products
        queryset = queryset.annotate(avg_rating=Avg('reviews__rating'))

        # Sorting
        if sort == 'price_asc':
            queryset = queryset.order_by('sale_price')
        elif sort == 'price_desc':
            queryset = queryset.order_by('-sale_price')
        elif sort == 'name_asc':
            queryset = queryset.order_by('products_name')
        elif sort == 'rating_desc':
            queryset = queryset.order_by('-avg_rating')
        elif sort == 'newest':
            queryset = queryset.order_by('-created_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        # Dynamic header
        search = request.GET.get('search')
        category_slug = request.GET.get('category')
        brand_slug = request.GET.get('brand')
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        sort = request.GET.get('sort', 'name_asc')

        if search:
            header = f"Search results for '{search}'"
        elif category_slug:
            category_obj = Category.objects.filter(slug=category_slug).first()
            header = f"Category: {category_obj.name}" if category_obj else "Category"
        elif brand_slug:
            brand_obj = Brand.objects.filter(slug=brand_slug).first()
            header = f"Brand: {brand_obj.name}" if brand_obj else "Brand"
        elif min_price or max_price:
            min_val = min_price or "0"
            max_val = max_price or "∞"
            header = f"Price: ${min_val} - ${max_val}"
        elif sort == 'newest':
            header = "Newest Products"
        else:
            header = "All Products"

        context['header_name'] = header

        # Categories and Brands for sidebar
        all_categories = Category.objects.all()
        all_brands = Brand.objects.all()
        category_counts = self.get_queryset().values('category').annotate(count=Count('category')).values_list('category', 'count')
        brand_counts = self.get_queryset().values('brand').annotate(count=Count('brand')).values_list('brand', 'count')

        context['categories'] = all_categories
        context['category_counts'] = dict(category_counts)
        context['brands'] = all_brands
        context['brand_counts'] = dict(brand_counts)

        # Extra product data
        for product in context['products']:
            product.stock_available = product.inventory_reverse.available_quantity if product.inventory_reverse else 0
            product.is_out_of_stock = product.stock_available <= 0
            product.thumbnail = product.products_image.url if product.products_image else (
                product.images.first().image.url if product.images.exists() else '/static/default.jpg'
            )
            product.avg_rating = product.avg_rating or 0
            product.current_price_display = product.current_price  # for template display

            # Calculate discount percentage
            if product.base_price and product.current_price < product.base_price:
                product.discount_percentage = round(
                    (product.base_price - product.current_price) / product.base_price * 100
                )
            else:
                product.discount_percentage = 0

        # Pass current filters & sort to template
        context['selected_category'] = category_slug
        context['selected_brand'] = brand_slug
        context['min_price'] = min_price
        context['max_price'] = max_price
        context['current_sort'] = sort

        return context

class ProductDetailView(DetailView):
    model = Product
    template_name = 'products/detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        # Add average rating and review count to context
        context['average_rating'] = product.reviews.filter(is_approved=True).aggregate(
            avg=Avg('rating')
        )['avg'] or 0
        context['review_count'] = product.reviews.filter(is_approved=True).count()
        return context



# def product_detail(request, slug):
#     """
#     Product detail page – also shows reviews and cart summary.
#     """
#     product = get_object_or_404(Product, slug=slug, is_active=True)
#     product = _calculate_discount(product)

#     # Cart for anonymous users only (authenticated users get order only)
#     if request.user.is_authenticated:
#         cart_items, cart_total = [], Decimal('0.00')
#         order = _get_user_order(request)
#     else:
#         order = None
#         cart_items, cart_total = _get_session_cart(request)

#     context = {
#         'product': product,
#         'reviews': product.reviews.filter(is_approved=True).select_related('user'),
#         'order': order,
#         'cart_items': cart_items,
#         'cart_total': cart_total,
#     }
#     return render(request, 'products/product_detail.html', context)


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


# In products/views.py or a utils file
def _calculate_discount(product):
    """
    Adds extra attributes to product for template use:
      - current_price
      - discount_percentage
    """
    # Current price logic
    product.current_price_display = product.current_price
    
    # Discount percentage
    if product.sale_price and product.sale_price < product.base_price:
        product.discount_percentage = round(
            (product.base_price - product.sale_price) / product.base_price * 100
        )
    else:
        product.discount_percentage = 0
    
    # Stock info
    product.stock_available = product.inventory_reverse.available_quantity if product.inventory_reverse else 0
    product.is_out_of_stock = product.stock_available <= 0
    
    return product
