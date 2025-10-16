# products/forms.py

from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'products_name', 'slug', 'product_code', 'brand', 'category', 'sub_category',
            'short_description', 'description', 'base_price', 'sale_price',
            'cost_price', 'color', 'size', 'weight', 'products_image', 'gallery_images',
            'meta_title', 'meta_description', 'is_active', 'is_featured', 'is_published', 
            'user', 'stock_managed_by_inventory'
        ]