# products/views.py
from decimal import Decimal
from typing import List, Tuple, Dict, Any
from django.db.models import Count

from django.shortcuts import render, get_object_or_404,redirect
from django.http import JsonResponse
from django.db.models import Q, Avg
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView

from products.models import Product, Review
from store.models import Category, Brand
from decimal import Decimal
from orders.models import OrderItem
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg




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
 
    products_qs = Product.objects.filter(is_active=True).select_related(
        'category', 
        'brand',
        'inventory_reverse'
    )
    
    # Calculate discounts for each product
    products = [calculate_discount(p) for p in products_qs]

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
    template_name = 'products/product_list.html'
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
        tag = self.request.GET.get('tag')
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        sort = self.request.GET.get('sort', )

        if search:
            queryset = queryset.filter(
                Q(products_name__icontains=search) |
                Q(description__icontains=search)
            )
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)
        if tag:
            queryset = queryset.filter(tags__icontains=tag)
        if min_price:
            queryset = queryset.filter(sale_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(sale_price__lte=max_price)

        # Annotate avg_rating for all products
        queryset = queryset.annotate(avg_rating=Avg('reviews__rating'))

        # Sorting (done while still a QuerySet)
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
        else:
        # Default: show highest rated items first
            queryset = queryset.order_by('-avg_rating')

        # Convert to list and calculate discount for template use
        queryset = [calculate_discount(p) for p in queryset]

        return queryset


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        for product in context['products']:
            if product.tags:
                # split tags by comma and strip whitespace
                product.tag_list = [t.strip() for t in product.tags.split(',')]
            else:
                product.tag_list = []

        # pass selected tag if filtering
        context['selected_tag'] = self.request.GET.get('tag')
        return context


class ProductDetailView(DetailView):
    model = Product
    template_name = 'products/detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object

        # ✅ Calculate discount & stock info
        product = calculate_discount(product)

        # Reviews
        reviews = product.reviews.filter(is_approved=True)
        context['reviews'] = reviews
        context['average_rating'] = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        context['review_count'] = reviews.count()

        # Can review logic (last 15 days)
        user = self.request.user
        can_review = False
        if user.is_authenticated:
            recent_purchase = OrderItem.objects.filter(
                order__user=user,
                product=product,
                order__created_at__gte=timezone.now() - timedelta(days=15)
            ).exists()
            has_already_reviewed = product.reviews.filter(user=user).exists()
            can_review = recent_purchase and not has_already_reviewed
        context['can_review'] = can_review

        # Tag list
        if product.tags:
            product.tag_list = [t.strip() for t in product.tags.split(',')]
        else:
            product.tag_list = []

        # Pass product with discount & stock info
        context['product'] = product

        # Optional: pass selected tag if filtering
        context['selected_tag'] = self.request.GET.get('tag')

        return context



@login_required(login_url='login')
def submit_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating', 0))
        except ValueError:
            rating = 0

        comment = request.POST.get('comment', '').strip()

        if rating <= 0 or rating > 5 or not comment:
            messages.error(request, "Please provide a valid rating and comment.")
            return redirect('products:product_detail', slug=product.slug)

        # Check recent purchase (within 15 days)
        recent_purchase = OrderItem.objects.filter(
            order__user=request.user,
            product=product,
            order__created_at__gte=timezone.now() - timedelta(days=15)
        ).exists()
        if not recent_purchase:
            messages.error(request, "You can only review a product within 15 days of purchasing it.")
            return redirect('products:product_detail', slug=product.slug)

        # Avoid duplicate review
        if Review.objects.filter(product=product, user=request.user).exists():
            messages.warning(request, "You’ve already reviewed this product.")
            return redirect('products:product_detail', slug=product.slug)

        Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            comment=comment,
            is_approved=False  # set True if no moderation
        )

        messages.success(request, "Thank you! Your review has been submitted.")
        return redirect('products:product_detail', slug=product.slug)

    return redirect('products:product_detail', slug=product.slug)


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

    products = [calculate_discount(p) for p in products_qs]

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


def calculate_discount(product):
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

