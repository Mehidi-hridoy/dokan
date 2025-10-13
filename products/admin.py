from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta
import json

from .models import Product, ProductImage, Review

class ProductImageInline(admin.TabularInline):
    model = Product.gallery_images.through
    extra = 1
    verbose_name = "Gallery Image"
    verbose_name_plural = "Gallery Images"

class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    readonly_fields = ['user', 'rating', 'title', 'comment', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Card View Display
    list_display = [
        'product_card',
        'products_name',
        'price_info',
        'stock_status',
        'category_brand',
        'status_badges',
        'quick_actions'
    ]
    
    list_display_links = None  # We'll handle links in the card
    list_per_page = 20
    
    # Filters and Search
    list_filter = [
        'is_active',
        'is_featured',
        'is_published',
        'category',
        'brand',
        'created_at'
    ]
    
    search_fields = [
        'products_name',
        'product_code',
        'category__name',
        'brand__name',
        'tags'
    ]
    
    # Inline editing
    inlines = [ProductImageInline, ReviewInline]
    
    # Fieldsets for detailed view
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'products_name',
                'slug',
                'product_code',
                'short_description',
                'description'
            )
        }),
        ('Categorization', {
            'fields': (
                'category',
                'sub_category',
                'brand',
                'user'
            )
        }),
        ('Pricing', {
            'fields': (
                'base_price',
                'sale_price',
                'cost_price'
            )
        }),
        ('Product Variants', {
            'fields': (
                'color',
                'size',
                'weight'
            ),
            'classes': ('collapse',)
        }),
        ('Images', {
            'fields': (
                'products_image',
            )
        }),
        ('SEO & Metadata', {
            'fields': (
                'meta_title',
                'meta_description',
                'tags'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': (
                'is_active',
                'is_featured',
                'is_published'
            )
        }),
    )
    
    readonly_fields = ['slug', 'product_code', 'created_at', 'updated_at']
    
    # Custom actions
    actions = [
        'activate_products',
        'deactivate_products',
        'mark_as_featured',
        'mark_as_not_featured',
        'publish_products',
        'unpublish_products',
        'update_prices_percentage'
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'category', 'brand', 'user'
        ).prefetch_related('inventory')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('quick-actions/<int:product_id>/<str:action>/', 
                 self.admin_site.admin_view(self.handle_quick_action),
                 name='products_quick_action'),
            path('bulk-price-update/', 
                 self.admin_site.admin_view(self.bulk_price_update_view),
                 name='products_bulk_price_update'),
            path('stock-report/', 
                 self.admin_site.admin_view(self.stock_report_view),
                 name='products_stock_report'),
        ]
        return custom_urls + urls
    
    # Custom list display methods for card view
    def product_card(self, obj):
        if obj.products_image:
            return format_html('<img src="{}" width="50" />', obj.products_image.url)
        return "-"
        # Stock status color
        if not obj.is_in_stock:
            stock_color = 'red'
            stock_text = 'Out of Stock'
        elif obj.is_low_stock:
            stock_color = 'orange'
            stock_text = 'Low Stock'
        else:
            stock_color = 'green'
            stock_text = 'In Stock'
        
        return format_html(
            '''
            <div class="product-card" style="display: flex; align-items: center; gap: 12px; padding: 8px 0;">
                <div style="flex-shrink: 0;">
                    <img src="{image_url}" alt="{name}" 
                         style="width: 60px; height: 60px; object-fit: cover; border-radius: 8px; border: 1px solid #e0e0e0;">
                </div>
                <div style="flex-grow: 1; min-width: 0;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
                        <strong style="font-size: 14px; color: #333; margin: 0; line-height: 1.3;">
                            <a href="{edit_url}" style="text-decoration: none; color: inherit;">{name}</a>
                        </strong>
                        <span class="stock-badge" style="background-color: {stock_color}; color: white; padding: 2px 8px; 
                              border-radius: 12px; font-size: 10px; font-weight: bold; white-space: nowrap;">
                            {stock_text}
                        </span>
                    </div>
                    <div style="font-size: 12px; color: #666; margin-bottom: 2px;">
                        <strong>Code:</strong> {code}
                    </div>
                    <div style="font-size: 12px; color: #888; line-height: 1.2;">
                        {short_desc}
                    </div>
                </div>
            </div>
            ''',
            image_url=image_url,
            name=obj.products_name,
            edit_url=f'{obj.id}/change/',
            stock_color=stock_color,
            stock_text=stock_text,
            code=obj.product_code,
            short_desc=(obj.short_description.raw[:80] + '...') if obj.short_description and obj.short_description.raw else 'No description'
        )
    product_card.short_description = 'Product'
    
    def price_info(self, obj):
        """Display pricing information"""
        if obj.sale_price and obj.sale_price < obj.base_price:
            price_html = f'''
                <div style="text-align: center;">
                    <div style="font-size: 14px; font-weight: bold; color: #e74c3c;">
                        ${obj.sale_price}
                    </div>
                    <div style="font-size: 11px; color: #999; text-decoration: line-through;">
                        ${obj.base_price}
                    </div>
                    <div style="font-size: 10px; color: #27ae60; font-weight: bold;">
                        -{((obj.base_price - obj.sale_price) / obj.base_price * 100):.0f}%
                    </div>
                </div>
            '''
        else:
            price_html = f'''
                <div style="text-align: center;">
                    <div style="font-size: 14px; font-weight: bold; color: #2c3e50;">
                        ${obj.base_price}
                    </div>
                    <div style="font-size: 11px; color: #7f8c8d;">
                        Regular
                    </div>
                </div>
            '''
        
        if obj.cost_price:
            margin = obj.profit_margin
            margin_color = '#27ae60' if margin and margin > 0 else '#e74c3c'
            margin_html = f'''
                <div style="font-size: 10px; color: {margin_color}; margin-top: 4px;">
                    Margin: {margin:.1f}% if margin else 'N/A'
                </div>
            '''
        else:
            margin_html = '<div style="font-size: 10px; color: #95a5a6;">No cost price</div>'
        
        return format_html(price_html + margin_html)
    price_info.short_description = 'Pricing'
    
    def stock_status(self, obj):
        """Display stock status with quantity"""
        if hasattr(obj, 'inventory'):
            quantity = obj.inventory.quantity
            threshold = obj.inventory.low_stock_threshold
            
            if quantity == 0:
                status_color = '#e74c3c'
                status_text = 'Out of Stock'
            elif quantity <= threshold:
                status_color = '#f39c12'
                status_text = f'Low ({quantity})'
            else:
                status_color = '#27ae60'
                status_text = f'Good ({quantity})'
        else:
            status_color = '#95a5a6'
            status_text = 'No Inventory'
        
        return format_html(
            '''
            <div style="text-align: center;">
                <div style="background-color: {color}; color: white; padding: 6px 12px; 
                      border-radius: 16px; font-size: 12px; font-weight: bold; display: inline-block;">
                    {text}
                </div>
            </div>
            ''',
            color=status_color,
            text=status_text
        )
    stock_status.short_description = 'Stock'
    
    def category_brand(self, obj):
        """Display category and brand"""
        category_html = f'<div style="font-size: 12px; font-weight: 500; color: #2c3e50;">{obj.category.name if obj.category else "No Category"}</div>'
        brand_html = f'<div style="font-size: 11px; color: #7f8c8d;">{obj.brand.name if obj.brand else "No Brand"}</div>'
        
        return format_html(category_html + brand_html)
    category_brand.short_description = 'Category & Brand'
    
    def status_badges(self, obj):
        """Display status badges"""
        badges = []
        
        if obj.is_active:
            badges.append('<span style="background-color: #27ae60; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px; margin: 1px;">Active</span>')
        else:
            badges.append('<span style="background-color: #e74c3c; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px; margin: 1px;">Inactive</span>')
        
        if obj.is_featured:
            badges.append('<span style="background-color: #f39c12; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px; margin: 1px;">Featured</span>')
        
        if obj.is_published:
            badges.append('<span style="background-color: #3498db; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px; margin: 1px;">Published</span>')
        else:
            badges.append('<span style="background-color: #95a5a6; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px; margin: 1px;">Draft</span>')
        
        return format_html(' '.join(badges))
    status_badges.short_description = 'Status'
    
    def quick_actions(self, obj):
        """Display quick action buttons"""
        return format_html(
            '''
            <div class="quick-actions" style="display: flex; flex-direction: column; gap: 4px;">
                <a href="{edit_url}" class="button" style="padding: 4px 8px; background: #3498db; color: white; 
                   text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center;">Edit</a>
                
                <a href="{view_url}" class="button" style="padding: 4px 8px; background: #2ecc71; color: white; 
                   text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center;" target="_blank">View</a>
                
                <button type="button" onclick="handleQuickAction({product_id}, 'toggle_active')" 
                        style="padding: 4px 8px; background: {active_color}; color: white; border: none; 
                        border-radius: 4px; font-size: 11px; cursor: pointer;">
                    {active_text}
                </button>
                
                <button type="button" onclick="handleQuickAction({product_id}, 'toggle_featured')" 
                        style="padding: 4px 8px; background: {featured_color}; color: white; border: none; 
                        border-radius: 4px; font-size: 11px; cursor: pointer;">
                    {featured_text}
                </button>
            </div>
            
            <script>
            function handleQuickAction(productId, action) {{
                fetch(`/admin/products/product/quick-actions/${{productId}}/${{action}}/`, {{
                    method: 'POST',
                    headers: {{
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'Content-Type': 'application/json',
                    }},
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        window.location.reload();
                    }} else {{
                        alert('Error: ' + data.error);
                    }}
                }});
            }}
            </script>
            ''',
            edit_url=f'{obj.id}/change/',
            view_url=f'{obj.slug}/',  # Adjust to your actual product URL
            product_id=obj.id,
            active_color='#e74c3c' if obj.is_active else '#2ecc71',
            active_text='Deactivate' if obj.is_active else 'Activate',
            featured_color='#e74c3c' if obj.is_featured else '#f39c12',
            featured_text='Unfeature' if obj.is_featured else 'Feature'
        )
    quick_actions.short_description = 'Actions'
    
    # Custom Actions
    def activate_products(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} products activated successfully.', messages.SUCCESS)
    activate_products.short_description = "Activate selected products"
    
    def deactivate_products(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} products deactivated.', messages.WARNING)
    deactivate_products.short_description = "Deactivate selected products"
    
    def mark_as_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} products marked as featured.', messages.SUCCESS)
    mark_as_featured.short_description = "Mark as featured"
    
    def mark_as_not_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} products unfeatured.', messages.WARNING)
    mark_as_not_featured.short_description = "Remove featured status"
    
    def publish_products(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(request, f'{updated} products published.', messages.SUCCESS)
    publish_products.short_description = "Publish selected products"
    
    def unpublish_products(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f'{updated} products unpublished.', messages.WARNING)
    unpublish_products.short_description = "Unpublish selected products"
    
    def update_prices_percentage(self, request, queryset):
        if 'apply' in request.POST:
            try:
                percentage = float(request.POST.get('percentage', 0))
                price_field = request.POST.get('price_field', 'base_price')
                
                for product in queryset:
                    if price_field == 'base_price':
                        current_price = getattr(product, 'base_price', 0)
                        new_price = current_price * (1 + percentage / 100)
                        product.base_price = new_price
                    elif price_field == 'sale_price' and product.sale_price:
                        current_price = product.sale_price
                        new_price = current_price * (1 + percentage / 100)
                        product.sale_price = new_price
                    
                    product.save()
                
                self.message_user(request, f'Updated prices for {queryset.count()} products.', messages.SUCCESS)
                return redirect(request.get_full_path())
            
            except ValueError:
                self.message_user(request, 'Invalid percentage value.', messages.ERROR)
                return redirect(request.get_full_path())
        
        return render(request, 'admin/products/update_prices.html', {
            'products': queryset,
            'action': 'update_prices_percentage'
        })
    update_prices_percentage.short_description = "Update prices by percentage"
    
    # Quick Actions Handler
    def handle_quick_action(self, request, product_id, action):
        try:
            product = Product.objects.get(id=product_id)
            
            if action == 'toggle_active':
                product.is_active = not product.is_active
                product.save()
            elif action == 'toggle_featured':
                product.is_featured = not product.is_featured
                product.save()
            elif action == 'toggle_published':
                product.is_published = not product.is_published
                product.save()
            
            return JsonResponse({'success': True})
        
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Product not found'})
    
    # Bulk Price Update View
    def bulk_price_update_view(self, request):
        if request.method == 'POST':
            # Handle bulk price update logic
            pass
        
        products = Product.objects.all()[:50]  # Limit for demo
        return render(request, 'admin/products/bulk_price_update.html', {
            'products': products,
            'title': 'Bulk Price Update'
        })
    
    # Stock Report View
    def stock_report_view(self, request):
        # Stock statistics
        total_products = Product.objects.count()
        in_stock = Product.objects.in_stock().count()
        low_stock = Product.objects.low_stock().count()
        out_of_stock = Product.objects.out_of_stock().count()
        
        # Recent products
        recent_products = Product.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        )[:10]
        
        return render(request, 'admin/products/stock_report.html', {
            'total_products': total_products,
            'in_stock': in_stock,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
            'recent_products': recent_products,
            'title': 'Stock Report'
        })

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['image_preview', 'product', 'alt_text', 'is_primary', 'display_order']
    list_filter = ['is_primary', 'product']
    search_fields = ['product__products_name', 'alt_text']
    list_editable = ['display_order', 'is_primary']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />',
                obj.image.url
            )
        return "No Image"
    image_preview.short_description = 'Preview'

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating_stars', 'title', 'is_approved', 'created_at']
    list_filter = ['rating', 'is_approved', 'created_at']
    search_fields = ['product__products_name', 'user__username', 'title']
    list_editable = ['is_approved']
    readonly_fields = ['created_at']
    
    def rating_stars(self, obj):
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html(
            '<span style="color: #f39c12; font-size: 14px;">{}</span>',
            stars
        )
    rating_stars.short_description = 'Rating'