from django.shortcuts import render
from products.models import Category, Brand, Product

def home(request):
    """Homepage view"""
    categories = Category.objects.filter(is_active=True, parent__isnull=True)[:8]
    featured_products = Product.objects.filter(
        status='published', 
        featured=True
    ).select_related('brand', 'category', 'inventory').prefetch_related('images')[:8]
    
    new_arrivals = Product.objects.filter(
        status='published'
    ).select_related('brand', 'category', 'inventory').prefetch_related('images').order_by('-created_at')[:8]
    
    brands = Brand.objects.filter(is_active=True)[:12]
    
    context = {
        'categories': categories,
        'featured_products': featured_products,
        'new_arrivals': new_arrivals,
        'brands': brands,
    }
    return render(request, 'store/home.html', context)

def about(request):
    """About page"""
    return render(request, 'store/about.html')

def contact(request):
    """Contact page"""
    return render(request, 'store/contact.html')