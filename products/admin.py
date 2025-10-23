# products/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.shortcuts import render
from .models import Product, ProductImage, Review

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'display_order']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(self, 'original') and self.original:
            return qs.filter(product=self.original)
        return qs

class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'products_name', 
        'product_code', 
        'category', 
        'base_price_display',
        'stock_status',
        'is_active',
        'quick_actions'
    ]
    list_filter = ['is_active', 'is_featured', 'category', 'brand']
    search_fields = ['products_name', 'product_code']
    readonly_fields = ['product_code', 'slug', 'created_at', 'updated_at', 'staff_permission_message']
    list_editable = ['is_active']
    inlines = [ProductImageInline]
    actions = ['activate_products', 'deactivate_products', 'feature_products', 'unfeature_products']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'staff_permission_message',
                'user', 'products_name', 'slug', 'product_code', 
                'short_description', 'description'
            )
        }),
        ('Categorization & Pricing', {
            'fields': (
                'category', 'sub_category', 'brand',
                'base_price', 'sale_price', 'cost_price'
            )
        }),
        ('Product Variants', {
            'fields': ('color', 'size', 'weight'),
            'classes': ('collapse',)
        }),
        ('Inventory & Stock', {
            'fields': ('stock_managed_by_inventory',),
            'classes': ('collapse',)
        }),
        ('Images', {
            'fields': ('products_image',),
            'classes': ('collapse',)
        }),
        ('SEO & Status', {
            'fields': (
                'meta_title', 'meta_description', 'tags',
                'is_active', 'is_featured', 'is_published'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'quick-add/',
                self.admin_site.admin_view(self.quick_add_view),
                name='products_product_quick_add',
            ),
        ]
        return custom_urls + urls
    
    def quick_add_view(self, request):
        """Quick product creation with minimal fields"""
        from store.models import Category, Brand
        
        if request.method == 'POST':
            try:
                # Create product with minimal data
                product = Product.objects.create(
                    products_name=request.POST.get('products_name'),
                    base_price=request.POST.get('base_price', 0),
                    category_id=request.POST.get('category'),
                    brand_id=request.POST.get('brand') or None,
                    short_description=request.POST.get('short_description', ''),
                    user=request.user,
                    is_active=request.POST.get('is_active') == 'on',
                    is_featured=request.POST.get('is_featured') == 'on',
                    is_published=request.POST.get('is_published') == 'on',
                )
                
                # Set optional prices
                if request.POST.get('sale_price'):
                    product.sale_price = request.POST.get('sale_price')
                if request.POST.get('cost_price'):
                    product.cost_price = request.POST.get('cost_price')
                product.save()
                
                messages.success(request, f'Product "{product.products_name}" created successfully!')
                return HttpResponseRedirect(f'../{product.pk}/change/')
                
            except Exception as e:
                messages.error(request, f'Error creating product: {str(e)}')
        
        context = {
            'categories': Category.objects.all(),
            'brands': Brand.objects.all(),
            'title': 'Quick Add Product',
            'opts': self.model._meta,
        }
        return render(request, 'admin/products/product/quick_add.html', context)
    
    def base_price_display(self, obj):
        return f"${obj.base_price}"
    base_price_display.short_description = 'Price'
    
    def stock_status(self, obj):
        if obj.is_in_stock:
            if obj.is_low_stock:
                return format_html('<span style="color: orange;">⚠ Low Stock</span>')
            return format_html('<span style="color: green;">✓ In Stock</span>')
        return format_html('<span style="color: red;">✗ Out of Stock</span>')
    stock_status.short_description = 'Stock'
    
    def quick_actions(self, obj):
        return format_html('<a href="{}">✏️ Edit</a>', f'{obj.id}/change/')
    quick_actions.short_description = 'Actions'
    
    def staff_permission_message(self, obj=None):
        if not obj:
            return format_html(
                '<div style="background: #d4edda; padding: 10px; border-radius: 5px; margin-bottom: 20px;">'
                '<strong>👨‍💼 Staff Permissions:</strong> You can create and edit products. '
                'Only administrators can delete products.'
                '</div>'
            )
        return format_html(
            '<div style="background: #d4edda; padding: 10px; border-radius: 5px; margin-bottom: 20px;">'
            '<strong>👨‍💼 Staff Permissions:</strong> You can edit this product. '
            'Only administrators can delete products.'
            '</div>'
        )
    staff_permission_message.short_description = ''
    
    # Custom actions
    def activate_products(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} products activated successfully.')
    activate_products.short_description = "Activate selected products"
    
    def deactivate_products(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} products deactivated successfully.')
    deactivate_products.short_description = "Deactivate selected products"
    
    def feature_products(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} products marked as featured.')
    feature_products.short_description = "Feature selected products"
    
    def unfeature_products(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} products unfeatured.')
    unfeature_products.short_description = "Remove featured status"

admin.site.register(Product, ProductAdmin)

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'image_tag', 'is_primary']
    
    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image.url)
        return "-"
    image_tag.short_description = 'Image'

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'is_approved', 'created_at']
    list_editable = ['is_approved']
    list_filter = ['is_approved', 'rating']