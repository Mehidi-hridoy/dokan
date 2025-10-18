from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from .models import Product, ProductImage, Review
from inventory.models import Inventory


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'display_order']
    readonly_fields = ['image_preview']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "-"
    image_preview.short_description = 'Preview'


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    readonly_fields = ['user', 'rating', 'title', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'products_name', 
        'product_code', 
        'color',
        'size', 
        'brand',
        'current_price_display',
        'stock_status',
        'is_active',
        'is_featured',
        'created_at'
    ]
    
    list_filter = [
        'is_active',
        'is_featured', 
        'is_published',
        'category',
        'brand',
        'color',
        'size',
        'created_at'
    ]
    
    search_fields = [
        'products_name',
        'product_code',
        'short_description',
        'description'
    ]
    
    readonly_fields = [
        'slug',
        'product_code',
        'profit_margin_display',
        'stock_info_display',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'products_name', 
                'slug', 
                'product_code',
                'user',
                'short_description',
                'description'
            )
        }),
        ('Categorization', {
            'fields': (
                'category',
                'sub_category', 
                'brand'
            )
        }),
        ('Pricing', {
            'fields': (
                'base_price',
                'sale_price', 
                'cost_price',
                'profit_margin_display'
            )
        }),
        ('Inventory & Variants', {
            'fields': (
                'inventory',
                'stock_managed_by_inventory',
                'stock_info_display',
                'color',
                'size', 
                'weight'
            )
        }),
        ('Media', {
            'fields': (
                'products_image',
                'gallery_images'
            )
        }),
        ('SEO', {
            'fields': (
                'meta_title',
                'meta_description',
                'tags'
            )
        }),
        ('Status', {
            'fields': (
                'is_active',
                'is_featured',
                'is_published'
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    inlines = [ProductImageInline, ReviewInline]
    
    actions = ['activate_products', 'deactivate_products', 'feature_products', 'unfeature_products']
    
    def current_price_display(self, obj):
        if obj.sale_price and obj.sale_price < obj.base_price:
            return format_html(
                '<span style="color: #d9534f;"><del>${}</del> ${}</span>',
                obj.base_price,
                obj.sale_price
            )
        return format_html('${}', obj.base_price)
    current_price_display.short_description = 'Price'
    current_price_display.admin_order_field = 'base_price'
    
    def stock_status(self, obj):
        if not obj.is_in_stock:
            return format_html('<span style="color: #d9534f; font-weight: bold;">Out of Stock</span>')
        elif obj.is_low_stock:
            return format_html('<span style="color: #f0ad4e; font-weight: bold;">Low Stock</span>')
        else:
            return format_html('<span style="color: #5cb85c; font-weight: bold;">In Stock</span>')
    stock_status.short_description = 'Stock Status'
    
    def profit_margin_display(self, obj):
        margin = obj.profit_margin
        if margin is not None:
            color = '#5cb85c' if margin > 0 else '#d9534f'
            return format_html('<span style="color: {}; font-weight: bold;">{:.1f}%</span>', color, margin)
        return "N/A"
    profit_margin_display.short_description = 'Profit Margin'
    
    def stock_info_display(self, obj):
        if hasattr(obj, 'inventory_reverse') and obj.inventory_reverse:
            inventory = obj.inventory_reverse
            return format_html(
                'Available: <strong>{}</strong><br>Low Stock Threshold: <strong>{}</strong><br>Low Stock: <strong>{}</strong>',
                inventory.available_quantity,
                inventory.low_stock_threshold,
                "Yes" if inventory.is_low_stock else "No"
            )
        return "No inventory data available"
    stock_info_display.short_description = 'Stock Information'
    
    def activate_products(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} products were successfully activated.')
    activate_products.short_description = "Activate selected products"
    
    def deactivate_products(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} products were successfully deactivated.')
    deactivate_products.short_description = "Deactivate selected products"
    
    def feature_products(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} products were successfully featured.')
    feature_products.short_description = "Feature selected products"
    
    def unfeature_products(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} products were successfully unfeatured.')
    unfeature_products.short_description = "Unfeature selected products"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'category', 'brand', 'inventory_reverse'
        ).prefetch_related('images', 'reviews')


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'image_preview', 'alt_text', 'is_primary', 'display_order']
    list_filter = ['is_primary', 'product__category']
    search_fields = ['product__products_name', 'alt_text']
    list_editable = ['is_primary', 'display_order']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "-"
    image_preview.short_description = 'Image'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating_stars', 'title', 'is_approved', 'created_at']
    list_filter = ['rating', 'is_approved', 'created_at', 'product__category']
    search_fields = ['product__products_name', 'user__username', 'title', 'comment']
    readonly_fields = ['created_at']
    list_editable = ['is_approved']
    actions = ['approve_reviews', 'disapprove_reviews']
    
    def rating_stars(self, obj):
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html('<span style="color: #ffd700; font-size: 14px;">{}</span>', stars)
    rating_stars.short_description = 'Rating'
    
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} reviews were successfully approved.')
    approve_reviews.short_description = "Approve selected reviews"
    
    def disapprove_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} reviews were successfully disapproved.')
    disapprove_reviews.short_description = "Disapprove selected reviews"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'user')