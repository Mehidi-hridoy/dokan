from django.shortcuts import render, get_object_or_404
from products.models import Product
from store.models import Category, Brand
from orders.models import Order

def home(request):
    products = Product.objects.filter(is_active=True,)
    for product in products:
        if product.previous_price and product.previous_price > product.price:
            product.discount_percentage = round(
                ((product.previous_price - product.price) / product.previous_price) * 100
            )
        else:
            product.discount_percentage = None
        product.tag_list = product.tags.split(', ') if product.tags else []
    
    categories = Category.objects.all()
    brands = Brand.objects.all()
    
    order = None
    if request.user.is_authenticated:
        order = Order.objects.filter(user=request.user, is_completed=False).first()
    
    context = {
        'products': products,
        'categories': categories,
        'brands': brands,
        'order': order,
    }
    return render(request, 'products/home.html', context)

def product_list(request):
    category_slug = request.GET.get('category')
    brand_slug = request.GET.get('brand')
    tag = request.GET.get('tag')

    products = Product.objects.filter(is_active=True)
    categories = Category.objects.all()
    brands = Brand.objects.all()

    selected_category = None
    selected_brand = None
    selected_tag = None
    header_name = "All Products"

    if category_slug:
        selected_category = category_slug
        category_obj = categories.filter(slug=category_slug).first()
        if category_obj:
            header_name = category_obj.name
            products = products.filter(category=category_obj)
    
    elif brand_slug:
        selected_brand = brand_slug
        brand_obj = brands.filter(slug=brand_slug).first()
        if brand_obj:
            header_name = brand_obj.name
            products = products.filter(brand=brand_obj)
    
    elif tag:
        selected_tag = tag
        header_name = f"Products tagged with: {tag}"
        products = products.filter(tags__icontains=tag)

    for product in products:
        if product.previous_price and product.previous_price > product.price:
            product.discount_percentage = round(
                ((product.previous_price - product.price) / product.previous_price) * 100
            )
        else:
            product.discount_percentage = None
        product.tag_list = product.tags.split(', ') if product.tags else []

    order = None
    if request.user.is_authenticated:
        order = Order.objects.filter(user=request.user, is_completed=False).first()

    context = {
        'products': products,
        'categories': categories,
        'brands': brands,
        'selected_category': selected_category,
        'selected_brand': selected_brand,
        'selected_tag': selected_tag,
        'header_name': header_name,
        'order': order,
    }
    return render(request, 'products/product_list.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    if product.previous_price and product.previous_price > product.price:
        product.discount_percentage = round(
            ((product.previous_price - product.price) / product.previous_price) * 100
        )
    else:
        product.discount_percentage = None
    product.tag_list = product.tags.split(', ') if product.tags else []
    reviews = product.reviews.all()
    
    order = None
    if request.user.is_authenticated:
        order = Order.objects.filter(user=request.user, is_completed=False).first()
    
    context = {
        'product': product,
        'reviews': reviews,
        'order': order,
    }
    return render(request, 'products/product_detail.html', context)