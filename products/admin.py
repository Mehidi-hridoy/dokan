from django.contrib import admin
from django.utils.html import format_html
from .models import Product, ProductImage
from django_ckeditor_5.widgets import CKEditor5Widget
from django import forms

# Form with CKEditor for product descriptions
class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'short_description': CKEditor5Widget(config_name='extends'),
            'description': CKEditor5Widget(config_name='extends'),
        }

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = (
        'name', 'product_code', 'image_tag', 'price', 'is_active', 
        'is_featured', 'stock_option', 'quantity', 'created_at'
    )
    list_filter = ('category', 'brand', 'is_active', 'is_featured', 'stock_option')
    search_fields = ('name', 'product_code',  'tags')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active', 'is_featured')
    filter_horizontal = ('gallery_images',)

    fieldsets = (
        (None, {'fields': ('name', 'slug', 'product_code', 'category', 'sub_category', 'brand', 'store')}),
        ('Pricing & Stock', {'fields': ('price', 'previous_price', 'stock_option', 'quantity', 'inventory')}),
        ('Details', {'fields': ('short_description', 'description', 'color', 'size', 'weight', 'unit')}),
        ('Images', {'fields': ('featured_image', 'gallery_images')}),
        ('SEO', {'fields': ('meta_title', 'meta_description', 'tags')}),
        ('Status', {'fields': ('is_active', 'is_featured')}),
    )

    # Custom method to display thumbnail
    def image_tag(self, obj):
        if obj.featured_image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;"/>', obj.featured_image.url)
        return "-"
    image_tag.short_description = 'Image'

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('alt_text', 'image')
    search_fields = ('alt_text',)
