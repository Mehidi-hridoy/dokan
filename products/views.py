# products/views.py
from decimal import Decimal
from typing import List, Tuple, Dict, Any
from django.db.models import Count
from .models import Product, Review,  COLOR_CHOICES, SIZE_CHOICES
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
from .utils import calculate_discount
from django.db.models import Exists, OuterRef




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
    # Get active products with related data
    products_qs = Product.objects.filter(is_active=True).select_related(
        'category', 
        'brand',
        'inventory_reverse'
    ).prefetch_related('images')

    # Calculate discounts for each product
    products = [calculate_discount(p) for p in products_qs]

    # Sort: in-stock first, then newest
    products = sorted(
        products, 
        key=lambda p: (not p.is_in_stock, -p.created_at.timestamp())
    )

    # Add color and size choices for dropdowns
    for p in products:
        p.color_choices = p._meta.get_field('color').choices if p.color else []
        p.size_choices = p._meta.get_field('size').choices if p.size else []

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
    paginate_by = 12

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).select_related(
            'category', 'brand', 'inventory_reverse'
        ).prefetch_related('images', 'reviews')

        queryset = queryset.annotate(avg_rating=Avg('reviews__rating'))

        # Check if user has reviewed this product
        if self.request.user.is_authenticated:
            user_reviews = Review.objects.filter(product=OuterRef('pk'), user=self.request.user)
            queryset = queryset.annotate(user_has_reviewed=Exists(user_reviews))

            # Check if user purchased this product AND 15 days have passed
            fifteen_days_ago = timezone.now() - timedelta(days=15)
            purchased_items = OrderItem.objects.filter(
                product=OuterRef('pk'),
                order__user=self.request.user,
                order__created_at__lte=fifteen_days_ago
            )
            queryset = queryset.annotate(user_can_review=Exists(purchased_items))

        else:
            queryset = queryset.annotate(
                user_has_reviewed=Exists(Product.objects.none()),
                user_can_review=Exists(Product.objects.none())
            )

        # --- Existing filter logic (unchanged) ---
        search_query = self.request.GET.get('search', '')
        category_slug = self.request.GET.get('category', '')
        brand_slug = self.request.GET.get('brand', '')
        tag = self.request.GET.get('tag', '')
        min_price = self.request.GET.get('min_price', '')
        max_price = self.request.GET.get('max_price', '')

        if search_query:
            queryset = queryset.filter(
                Q(products_name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(short_description__icontains=search_query)
            )
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)
        if tag:
            queryset = queryset.filter(tags__icontains=tag)
        if min_price:
            queryset = queryset.filter(sale_price__gte=Decimal(min_price))
        if max_price:
            queryset = queryset.filter(sale_price__lte=Decimal(max_price))

        # Sorting
        sort = self.request.GET.get('sort', 'rating_desc')
        if sort == 'name_asc':
            queryset = queryset.order_by('products_name')
        elif sort == 'price_asc':
            queryset = queryset.order_by('sale_price')
        elif sort == 'price_desc':
            queryset = queryset.order_by('-sale_price')
        elif sort == 'rating_desc':
            queryset = queryset.order_by('-avg_rating')
        elif sort == 'newest':
            queryset = queryset.order_by('-created_at')
        else:
            queryset = queryset.order_by('-avg_rating')

        return queryset
    
    # --- START OF NEW/MODIFIED CODE ---
    
    def get_context_data(self, **kwargs):
        """
        Adds the COLOR_CHOICES and SIZE_CHOICES to each product object 
        in the context for template rendering of dropdowns.
        """
        # Call the base implementation first to get the context
        context = super().get_context_data(**kwargs)
        
        # Access the list of products from the context
        products = context.get(self.context_object_name)
        
        if products:
            
            for product in products:
                # Assuming COLOR_CHOICES and SIZE_CHOICES are imported from .models
                product.color_choices = COLOR_CHOICES 
                product.size_choices = SIZE_CHOICES
                
        return context
    



class ProductDetailView(DetailView):
    model = Product
    template_name = 'products/detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object

        # Calculate discount
        product = calculate_discount(product)

        # Only approved reviews
        reviews = product.reviews.filter(is_approved=True)
        context['reviews'] = reviews
        context['average_rating'] = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        context['review_count'] = reviews.count()

        # Add color/size/weight choices for dropdowns
        product.color_choices = product._meta.get_field('color').choices if product.color else []
        product.size_choices = product._meta.get_field('size').choices if product.size else []
        product.weight_choices = product._meta.get_field('weight').choices if product.weight else []

        # User review logic
        user = self.request.user
        can_review = False
        user_review = None
        if user.is_authenticated:
            purchased = OrderItem.objects.filter(
                order__user=user,
                product=product,
                order__payment_status='Paid'
            ).exists()
            existing_review = product.reviews.filter(user=user).first()
            can_review = purchased and (existing_review is None)
            user_review = existing_review

        context['can_review'] = can_review
        context['user_review'] = user_review

        # Tags
        context['product'].tag_list = [t.strip() for t in (product.tags or "").split(",")]

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


def add_review(request):
    if not request.user.is_authenticated:
        messages.error(request, "Please log in to submit a review.")
        return redirect('login')
    if request.method == 'POST':
        product_slug = request.POST.get('product_slug')
        rating = request.POST.get('rating')
        title = request.POST.get('title')
        comment = request.POST.get('comment')
        try:
            product = Product.objects.get(slug=product_slug)
            if Review.objects.filter(user=request.user, product=product).exists():
                messages.error(request, "You have already reviewed this product.")
            else:
                Review.objects.create(
                    user=request.user,
                    product=product,
                    rating=rating,
                    title=title,
                    comment=comment,
                    is_approved=False
                )
                messages.success(request, "Review submitted. It will appear after approval.")
        except Product.DoesNotExist:
            messages.error(request, "Product not found.")
        return redirect('products:product_list')
    return redirect('products:product_list')