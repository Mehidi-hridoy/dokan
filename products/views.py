from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Avg, Count, Prefetch
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Product, Category, Brand, ProductReview, Wishlist
from .forms import ProductReviewForm

def product_list(request):
    """Display all products with filtering and sorting"""
    products = Product.objects.filter(status='published').select_related(
        'category', 'brand', 'inventory'
    ).prefetch_related('images')
    
    # Filtering
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug, is_active=True)
        products = products.filter(category=category)
    
    brand_slug = request.GET.get('brand')
    if brand_slug:
        brand = get_object_or_404(Brand, slug=brand_slug, is_active=True)
        products = products.filter(brand=brand)
    
    # Price filtering
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    
    # Search
    search_query = request.GET.get('q')
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(short_description__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(category__name__icontains=search_query) |
            Q(brand__name__icontains=search_query) |
            Q(tags__icontains=search_query)
        )
    
    # Sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'price_low':
        products = products.order_by('price')
    elif sort_by == 'price_high':
        products = products.order_by('-price')
    elif sort_by == 'name':
        products = products.order_by('name')
    elif sort_by == 'popular':
        products = products.annotate(review_count=Count('reviews')).order_by('-review_count')
    else:  # newest
        products = products.order_by('-created_at')
    
    # Get filter counts
    categories = Category.objects.filter(is_active=True).annotate(
        product_count=Count('products', filter=Q(products__status='published'))
    )
    brands = Brand.objects.filter(is_active=True).annotate(
        product_count=Count('products', filter=Q(products__status='published'))
    )
    
    # Pagination
    paginator = Paginator(products, 20)  # 20 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'brands': brands,
        'selected_category': category_slug,
        'selected_brand': brand_slug,
        'search_query': search_query,
        'sort_by': sort_by,
        'min_price': min_price,
        'max_price': max_price,
    }
    return render(request, 'products/product_list.html', context)

def product_search(request):
    """Handle product search - redirect to product list with search parameters"""
    query = request.GET.get('q', '')
    return redirect('products:product_list') + f'?q={query}'

def product_detail(request, slug):
    """Display product details"""
    product = get_object_or_404(
        Product.objects.select_related('category', 'brand', 'inventory')
                       .prefetch_related(
                           'images',
                           Prefetch('reviews', queryset=ProductReview.objects.filter(is_approved=True).select_related('user'))
                       ),
        slug=slug,
        status='published'
    )
    
    # Get average rating and review count
    rating_stats = product.reviews.aggregate(
        avg_rating=Avg('rating'),
        review_count=Count('id')
    )
    avg_rating = rating_stats['avg_rating'] or 0
    review_count = rating_stats['review_count']
    
    # Get rating distribution
    rating_distribution = {}
    for i in range(1, 6):
        rating_distribution[i] = product.reviews.filter(rating=i).count()
    
    # Related products (same category, excluding current product)
    related_products = Product.objects.filter(
        category=product.category,
        status='published'
    ).exclude(id=product.id).select_related('category', 'brand', 'inventory').prefetch_related('images')[:4]
    
    # Check if user has already reviewed this product
    user_review = None
    if request.user.is_authenticated:
        user_review = product.reviews.filter(user=request.user).first()
    
    # Check if product is in user's wishlist
    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()
    
    context = {
        'product': product,
        'related_products': related_products,
        'avg_rating': avg_rating,
        'review_count': review_count,
        'rating_distribution': rating_distribution,
        'user_review': user_review,
        'in_wishlist': in_wishlist,
        'review_form': ProductReviewForm(),
    }
    return render(request, 'products/product_detail.html', context)

def category_products(request, slug):
    """Display products by category"""
    category = get_object_or_404(Category, slug=slug, is_active=True)
    
    # Get products in this category and subcategories
    products = Product.objects.filter(
        Q(category=category) | Q(category__parent=category),
        status='published'
    ).select_related('category', 'brand', 'inventory').prefetch_related('images')
    
    # Get subcategories
    subcategories = Category.objects.filter(parent=category, is_active=True).annotate(
        product_count=Count('products', filter=Q(products__status='published'))
    )
    
    # Sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'price_low':
        products = products.order_by('price')
    elif sort_by == 'price_high':
        products = products.order_by('-price')
    elif sort_by == 'name':
        products = products.order_by('name')
    else:  # newest
        products = products.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'page_obj': page_obj,
        'subcategories': subcategories,
        'sort_by': sort_by,
    }
    return render(request, 'products/category_products.html', context)

def brand_products(request, slug):
    """Display products by brand"""
    brand = get_object_or_404(Brand, slug=slug, is_active=True)
    
    products = Product.objects.filter(
        brand=brand,
        status='published'
    ).select_related('category', 'brand', 'inventory').prefetch_related('images')
    
    # Sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'price_low':
        products = products.order_by('price')
    elif sort_by == 'price_high':
        products = products.order_by('-price')
    elif sort_by == 'name':
        products = products.order_by('name')
    else:  # newest
        products = products.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'brand': brand,
        'page_obj': page_obj,
        'sort_by': sort_by,
    }
    return render(request, 'products/brand_products.html', context)

def category_list(request):
    """Display all categories"""
    categories = Category.objects.filter(
        is_active=True,
        parent__isnull=True
    ).annotate(
        product_count=Count('products', filter=Q(products__status='published'))
    ).prefetch_related('children')
    
    context = {
        'categories': categories,
    }
    return render(request, 'products/category_list.html', context)

def brand_list(request):
    """Display all brands"""
    brands = Brand.objects.filter(is_active=True).annotate(
        product_count=Count('products', filter=Q(products__status='published'))
    )
    
    context = {
        'brands': brands,
    }
    return render(request, 'products/brand_list.html', context)

@login_required
def submit_review(request, product_id):
    """Handle product review submission"""
    product = get_object_or_404(Product, id=product_id, status='published')
    
    if request.method == 'POST':
        form = ProductReviewForm(request.POST)
        if form.is_valid():
            # Check if user already reviewed this product
            existing_review = ProductReview.objects.filter(
                user=request.user,
                product=product
            ).first()
            
            if existing_review:
                # Update existing review
                existing_review.rating = form.cleaned_data['rating']
                existing_review.title = form.cleaned_data['title']
                existing_review.comment = form.cleaned_data['comment']
                existing_review.is_approved = False  # Require re-approval for updates
                existing_review.save()
                messages.success(request, 'Your review has been updated and is pending approval.')
            else:
                # Create new review
                review = form.save(commit=False)
                review.product = product
                review.user = request.user
                review.save()
                messages.success(request, 'Thank you for your review! It is pending approval.')
            
            return redirect('products:product_detail', slug=product.slug)
    else:
        form = ProductReviewForm()
    
    return redirect('products:product_detail', slug=product.slug)

@login_required
def wishlist_view(request):
    """Display user's wishlist"""
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related(
        'product', 'product__category', 'product__brand', 'product__inventory'
    ).prefetch_related('product__images')
    
    context = {
        'wishlist_items': wishlist_items,
    }
    return render(request, 'products/wishlist.html', context)

@login_required
def add_to_wishlist(request, product_id):
    """Add product to user's wishlist"""
    product = get_object_or_404(Product, id=product_id, status='published')
    
    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        product=product
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'action': 'added',
            'wishlist_count': Wishlist.objects.filter(user=request.user).count()
        })
    
    messages.success(request, f'{product.name} has been added to your wishlist.')
    return redirect('products:product_detail', slug=product.slug)

@login_required
def remove_from_wishlist(request, product_id):
    """Remove product from user's wishlist"""
    product = get_object_or_404(Product, id=product_id)
    
    Wishlist.objects.filter(user=request.user, product=product).delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'action': 'removed',
            'wishlist_count': Wishlist.objects.filter(user=request.user).count()
        })
    
    messages.success(request, f'{product.name} has been removed from your wishlist.')
    
    # Redirect back to previous page or wishlist
    next_url = request.META.get('HTTP_REFERER', 'products:wishlist')
    return redirect(next_url)

def product_quick_view(request, product_id):
    """Return product details for quick view modal"""
    product = get_object_or_404(
        Product.objects.select_related('category', 'brand', 'inventory')
                       .prefetch_related('images'),
        id=product_id,
        status='published'
    )
    
    context = {
        'product': product,
    }
    return render(request, 'products/partials/quick_view.html', context)