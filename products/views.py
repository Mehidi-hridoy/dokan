# products/views.py

from decimal import Decimal
from typing import List, Tuple, Dict, Any
from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Avg, Count, Exists, OuterRef
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.utils import timezone

from .models import Product, Review, COLOR_CHOICES, SIZE_CHOICES
from .utils import calculate_discount
from store.models import Category, Brand
from orders.models import OrderItem



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



def home(request, category_slug=None, brand_slug=None):
    """
    Home page view:
    - Displays active products, sorted in-stock first, then newest
    - Supports optional category or brand filtering by slug
    """
    
    products_qs = Product.objects.filter(is_active=True).select_related(
        'category', 'brand', 'inventory_reverse'
    ).prefetch_related('images')
    
    # Filter by category if slug provided
    if category_slug:
        products_qs = products_qs.filter(category__slug=category_slug)
    
    # Filter by brand if slug provided
    if brand_slug:
        products_qs = products_qs.filter(brand__slug=brand_slug)

    # Get featured products - using the is_featured field from your model
    featured_products_qs = Product.objects.filter(
        is_active=True,
        is_featured=True
    ).select_related(
        'category', 'brand', 'inventory_reverse'
    ).prefetch_related('images')[:8]  # Limit to 8 featured products

    # Calculate discounts
    products = [calculate_discount(p) for p in products_qs]
    featured_products = [calculate_discount(p) for p in featured_products_qs]

    # Sort: in-stock first, then newest
    products = sorted(
        products,
        key=lambda p: (not p.is_in_stock, -p.created_at.timestamp())
    )

    # Add color and size choices to main products
    for p in products:
        p.color_choices = p._meta.get_field('color').choices if hasattr(p, 'color') and p.color else []
        p.size_choices = p._meta.get_field('size').choices if hasattr(p, 'size') and p.size else []

    # Add color and size choices to featured products
    for p in featured_products:
        p.color_choices = p._meta.get_field('color').choices if hasattr(p, 'color') and p.color else []
        p.size_choices = p._meta.get_field('size').choices if hasattr(p, 'size') and p.size else []

    # Categories and brands for sidebar / navigation
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
        'featured_products': featured_products,  # Add featured products to context
        'categories': categories,
        'brands': brands,
        'order': order,
        'cart_items': cart_items,
        'cart_total': cart_total,
        'current_category': category_slug,
        'current_brand': brand_slug,
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

        # --- Filter logic ---
        category_slug = self.request.GET.get('category', '')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        # Existing filters...
        search_query = self.request.GET.get('search', '')
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        
        # Process products to add necessary attributes
        products = context['products']
        processed_products = []
        
        for product in products:
            # Calculate discount
            product = calculate_discount(product)
            
            # Add color and size choices
            product.color_choices = product._meta.get_field('color').choices if hasattr(product, 'color') and product.color else []
            product.size_choices = product._meta.get_field('size').choices if hasattr(product, 'size') and product.size else []
            
            processed_products.append(product)
        
        context['products'] = processed_products
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


def category_filter(request, category_slug):
    category = get_object_or_404(Category, slug=category_slug)
    products = Product.objects.filter(category=category, is_active=True)
    return render(request, 'products/category_products.html', {
        'category': category,
        'products': products
    })

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
    Search by product name or description.
    """
    query = request.GET.get('q', '').strip()
    products_qs = Product.objects.filter(is_active=True).select_related('category', 'brand')

    if query:
        products_qs = products_qs.filter(
            Q(products_name__icontains=query) |
            Q(description__icontains=query) |
            Q(short_description__icontains=query) |
            Q(category__name__icontains=query) |
            Q(brand__name__icontains=query)
        )
    else:
        # If no query, return some featured products or empty
        products_qs = Product.objects.filter(is_active=True, is_featured=True)[:12]

    # Regular search results
    products = [calculate_discount(p) for p in products_qs]

    # Add color and size choices for template
    for product in products:
        product.color_choices = product._meta.get_field('color').choices if hasattr(product, 'color') and product.color else []
        product.size_choices = product._meta.get_field('size').choices if hasattr(product, 'size') and product.size else []
        
        # Add main image for template display
        product.main_image_url = get_product_main_image(product)

    # Cart handling
    if request.user.is_authenticated:
        order = _get_user_order(request)
        cart_items, cart_total = [], Decimal('0.00')
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

# Helper function to get main product image
def get_product_main_image(product):
    """
    Get the main image URL for a product, handling different field structures
    """
    try:
        # Method 1: Check images relation
        if hasattr(product, 'images') and product.images.exists():
            first_image = product.images.first()
            if first_image and hasattr(first_image, 'image') and first_image.image:
                return first_image.image.url
        
        # Method 2: Check direct image fields
        image_fields = ['image', 'main_image', 'thumbnail', 'product_image']
        for field in image_fields:
            if hasattr(product, field):
                field_value = getattr(product, field)
                if field_value:
                    return field_value.url
        
        # Method 3: Default image
        return '/static/images/default-product.jpg'
    except Exception as e:
        print(f"Error getting image for product {product.id}: {e}")
        return '/static/images/default-product.jpg'



def search_suggestions(request):
    """
    AJAX view for search suggestions (returns JSON)
    """
    query = request.GET.get('q', '').strip()
    suggestions = []
    
    if len(query) >= 1:  # Changed to 1 character for immediate feedback
        products = Product.objects.filter(
            Q(products_name__icontains=query) |
            Q(description__icontains=query) |
            Q(short_description__icontains=query) |
            Q(category__name__icontains=query) |
            Q(brand__name__icontains=query),
            is_active=True
        )[:8]  # Limit to 8 suggestions
        
        for product in products:
            # Get the first image from the images relation or use default
            image_url = ''
            try:
                if product.images.exists():
                    # Get the first image from the related images
                    first_image = product.images.first()
                    if first_image and hasattr(first_image, 'image') and first_image.image:
                        image_url = first_image.image.url
                else:
                    # Try other possible image fields
                    if hasattr(product, 'main_image') and product.main_image:
                        image_url = product.main_image.url
                    elif hasattr(product, 'thumbnail') and product.thumbnail:
                        image_url = product.thumbnail.url
                    else:
                        image_url = '/static/images/default-product.jpg'
            except Exception as e:
                # Fallback if any image processing fails
                image_url = '/static/images/default-product.jpg'
                print(f"Image error for product {product.id}: {e}")
            
            # Get the correct price - handle both sale_price and price fields
            price = '0.00'
            if hasattr(product, 'sale_price') and product.sale_price:
                price = str(product.sale_price)
            elif hasattr(product, 'price') and product.price:
                price = str(product.price)
            elif hasattr(product, 'current_price') and product.current_price:
                price = str(product.current_price)
            elif hasattr(product, 'base_price') and product.base_price:
                price = str(product.base_price)
            
            suggestions.append({
                'name': product.products_name,
                'url': product.get_absolute_url(),
                'price': price,
                'image': image_url
            })
    
    return JsonResponse({'suggestions': suggestions})



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