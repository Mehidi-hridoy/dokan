# products/admin.py

from django.contrib import admin
from django.utils.html import format_html
from decimal import Decimal # Needed if profit_margin_display is restored

from .models import Product, ProductImage, Review


# ----------------------------------------------------------------------
# Inline for ProductImage
# ----------------------------------------------------------------------
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'alt_text', 'is_primary', 'display_order')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 80px; max-width: 80px;" />',
                obj.image.url
            )
        return "(No image)"
    image_preview.short_description = "Preview"


# ----------------------------------------------------------------------
# Simple Admin for Product
# ----------------------------------------------------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # This class will automatically use ProductForm if form = ProductForm is NOT specified
    
    # --- List View ---
    list_display = (
        'products_name', 'product_code', 'category', 'brand', 
        'base_price', 'sale_price', 'is_active', 'is_published',
        'created_at'
    )
    list_filter = ('is_active', 'is_published', 'category', 'brand')
    search_fields = ('products_name', 'product_code', 'description')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    # --- Form View (CRITICAL FIX FOR KeyError: 'slug') ---
    fieldsets = (
        (None, {
            # 'slug' MUST be listed here to resolve the KeyError due to prepopulated_fields
            'fields': ('user', 'products_name', 'slug', 'product_code')
        }),
        ('Descriptions', {'fields': ('short_description', 'description')}),
        ('Categorization', {'fields': ('category', 'sub_category', 'brand')}),
        ('Pricing', {'fields': ('base_price', 'sale_price', 'cost_price')}),
        ('Variants', {'fields': ('color', 'size', 'weight')}),
        ('Stock Status', {'fields': ('stock_managed_by_inventory',)}),
        ('Images', {'fields': ('products_image',)}),
        ('Status', {'fields': ('is_active', 'is_featured', 'is_published')}),
        ('SEO', {'fields': ('meta_title', 'meta_description', 'tags')}),
    )

    readonly_fields = ('slug', 'product_code', 'tags', 'created_at', 'updated_at')
    prepopulated_fields = {"slug": ("products_name",)}
    inlines = [ProductImageInline]

    # --- Optimization and Data Hooks ---
    def save_model(self, request, obj, form, change):
        # Allow the model's save method to handle sale_price logic
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        # Optimized query with the corrected related name 'inventory_reverse'
        qs = super().get_queryset(request)
        return qs.select_related('category', 'brand', 'inventory_reverse')


# ----------------------------------------------------------------------
# Simple Admin for ProductImage
# ----------------------------------------------------------------------
@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'alt_text', 'is_primary', 'display_order')
    list_filter = ('is_primary',)
    search_fields = ('product__products_name', 'alt_text')


# ----------------------------------------------------------------------
# Simple Admin for Review
# ----------------------------------------------------------------------
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'title', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'rating')
    search_fields = ('product__products_name', 'user__username', 'title', 'comment')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('product', 'user', 'rating', 'title', 'comment')}),
        ('Moderation', {'fields': ('is_approved',)}),
    )
    readonly_fields = ('created_at',)