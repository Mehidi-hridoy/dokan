
from django.shortcuts import render
from products.models import Product

def home(request):
    products = Product.objects.filter(is_active=True,)
    return render(request, 'products/home.html', {'products': products})