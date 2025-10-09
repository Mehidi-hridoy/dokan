
from django.shortcuts import render
from products.models import Product
from store.models import Category, Brand

def home(request):
    products = Product.objects.filter(is_active=True,)
    return render(request, 'products/home.html', {'products': products})


# products/views.py
def product_list(request):
    category_slug = request.GET.get('category')
    brand_slug = request.GET.get('brand')

    products = Product.objects.filter(is_active=True)
    categories = Category.objects.all()
    brands = Brand.objects.all()

    selected_category = None
    selected_brand = None
    header_name = "All Products"

    if category_slug:
        selected_category = category_slug
        category_obj = categories.filter(slug=category_slug).first()
        if category_obj:
            header_name = category_obj.name

    elif brand_slug:
        selected_brand = brand_slug
        brand_obj = brands.filter(slug=brand_slug).first()
        if brand_obj:
            header_name = brand_obj.name

    context = {
        'products': products,
        'categories': categories,
        'brands': brands,
        'selected_category': selected_category,
        'selected_brand': selected_brand,
        'header_name': header_name,
        # include pagination / sorting context as needed
    }
    return render(request, 'products/product_list.html', context)
