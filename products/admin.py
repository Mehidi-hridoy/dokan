from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg, Q
from .models import *

class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 1
    ordering = ['ordering']

@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'type', 'value_count', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [AttributeValueInline]
    
    def value_count(self, obj):
        return obj.values.count()
    value_count.short_description = 'Values'

@admin.register(AttributeValue)
class AttributeValueAdmin(admin.ModelAdmin):
    list_display = ['attribute', 'value', 'color_code', 'ordering']
    list_filter = ['attribute']
    search_fields = ['value', 'attribute__name']
    list_editable = ['ordering']

class CategoryInline(admin.TabularInline):
    model = Category
    fields = ['name', 'slug', 'is_active']
    extra = 0
    show_change_link = True

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent', 'product_count', 'is_active', 'ordering']
    list_filter = ['is_active', 'parent', 'created_at']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['ordering', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'product_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    readonly_fields = ['preview_image']
    
    def preview_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "-"
    preview_image.short_description = 'Preview'

class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1
    autocomplete_fields = ['attribute']

class VariantAttributeInline(admin.TabularInline):
    model = VariantAttribute
    extra = 1
    autocomplete_fields = ['attribute_value']

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    readonly_fields = ['variant_attributes']
    show_change_link = True
    
    def variant_attributes(self, obj):
        attributes = obj.attributes.all()
        if attributes:
            return ", ".join([str(attr) for attr in attributes])
        return "-"
    variant_attributes.short_description = 'Attributes'

class InventoryInline(admin.StackedInline):
    model = Inventory
    extra = 1
    fields = ['quantity', 'low_stock_threshold', 'reorder_level', 'reserved_quantity', 'stock_status']
    readonly_fields = ['stock_status']
    
    def stock_status(self, obj):
        if obj.quantity == 0:
            return format_html('<span style="color: red; font-weight: bold;">Out of Stock</span>')
        elif obj.is_low_stock:
            return format_html('<span style="color: orange; font-weight: bold;">Low Stock</span>')
        else:
            return format_html('<span style="color: green; font-weight: bold;">In Stock</span>')
    stock_status.short_description = 'Status'

# Custom Admin Filters
class LowStockFilter(admin.SimpleListFilter):
    title = 'stock status'
    parameter_name = 'stock_status'
    
    def lookups(self, request, model_admin):
        return (
            ('low', 'Low Stock'),
            ('out', 'Out of Stock'),
            ('normal', 'Normal Stock'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(inventory__quantity__lte=models.F('inventory__low_stock_threshold'), inventory__quantity__gt=0)
        elif self.value() == 'out':
            return queryset.filter(inventory__quantity=0)
        elif self.value() == 'normal':
            return queryset.filter(inventory__quantity__gt=models.F('inventory__low_stock_threshold'))
        return queryset

class HasInventoryFilter(admin.SimpleListFilter):
    title = 'inventory status'
    parameter_name = 'inventory_status'
    
    def lookups(self, request, model_admin):
        return (
            ('has_inventory', 'Has Inventory'),
            ('no_inventory', 'No Inventory'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'has_inventory':
            return queryset.filter(inventory__isnull=False)
        elif self.value() == 'no_inventory':
            return queryset.filter(inventory__isnull=True)
        return queryset

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'sku', 
        'category', 
        'brand', 
        'price', 
        'stock_status', 
        'status', 
        'featured', 
        'created_at'
    ]
    list_filter = [
        'status', 
        'featured', 
        'category', 
        'brand', 
        'type',
        'created_at',
        LowStockFilter,
        HasInventoryFilter,
    ]
    search_fields = [
        'name', 
        'sku', 
        'description', 
        'category__name', 
        'brand__name'
    ]
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['status', 'featured', 'price']
    readonly_fields = ['created_at', 'updated_at', 'discount_percentage_display']
    inlines = [ProductImageInline, ProductAttributeInline, ProductVariantInline, InventoryInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'sku', 'type', 'description', 'short_description')
        }),
        ('Pricing', {
            'fields': ('price', 'compare_price', 'cost_price', 'discount_percentage_display')
        }),
        ('Categorization', {
            'fields': ('category', 'brand', 'tags')
        }),
        ('Status & Features', {
            'fields': ('status', 'featured', 'track_inventory')
        }),
        ('Physical Properties', {
            'fields': ('weight', 'length', 'width', 'height'),
            'classes': ('collapse',)
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def stock_status(self, obj):
        if hasattr(obj, 'inventory'):
            inventory = obj.inventory
            if inventory.quantity == 0:
                return format_html('<span style="color: red;">❌ Out of Stock</span>')
            elif inventory.is_low_stock:
                return format_html('<span style="color: orange;">⚠️ Low Stock</span>')
            else:
                return format_html('<span style="color: green;">✅ In Stock</span>')
        return format_html('<span style="color: gray;">─</span>')
    stock_status.short_description = 'Stock'
    
    def discount_percentage_display(self, obj):
        if obj.discount_percentage > 0:
            return format_html('<span style="color: green; font-weight: bold;">{}% OFF</span>', obj.discount_percentage)
        return "-"
    discount_percentage_display.short_description = 'Discount'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'category', 'brand', 'inventory'
        ).prefetch_related('images')
    
    actions = ['make_published', 'make_draft', 'toggle_featured']
    
    def make_published(self, request, queryset):
        updated = queryset.update(status='published')
        self.message_user(request, f'{updated} products were successfully published.')
    make_published.short_description = "Mark selected products as published"
    
    def make_draft(self, request, queryset):
        updated = queryset.update(status='draft')
        self.message_user(request, f'{updated} products were marked as draft.')
    make_draft.short_description = "Mark selected products as draft"
    
    def toggle_featured(self, request, queryset):
        for product in queryset:
            product.featured = not product.featured
            product.save()
        self.message_user(request, f'Featured status toggled for {queryset.count()} products.')
    toggle_featured.short_description = "Toggle featured status"

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['sku', 'product', 'price', 'stock_status', 'is_default']
    list_filter = ['is_default', 'created_at']
    search_fields = ['sku', 'product__name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [VariantAttributeInline]
    
    def stock_status(self, obj):
        if hasattr(obj, 'inventory'):
            inventory = obj.inventory
            if inventory.quantity == 0:
                return format_html('<span style="color: red;">Out of Stock</span>')
            elif inventory.is_low_stock:
                return format_html('<span style="color: orange;">Low Stock</span>')
            else:
                return format_html('<span style="color: green;">In Stock</span>')
        return "-"
    stock_status.short_description = 'Stock'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'inventory')

class VariantLowStockFilter(admin.SimpleListFilter):
    title = 'stock status'
    parameter_name = 'stock_status'
    
    def lookups(self, request, model_admin):
        return (
            ('low', 'Low Stock'),
            ('out', 'Out of Stock'),
            ('normal', 'Normal Stock'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(inventory__quantity__lte=models.F('inventory__low_stock_threshold'), inventory__quantity__gt=0)
        elif self.value() == 'out':
            return queryset.filter(inventory__quantity=0)
        elif self.value() == 'normal':
            return queryset.filter(inventory__quantity__gt=models.F('inventory__low_stock_threshold'))
        return queryset

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity', 'available_quantity', 'reserved_quantity', 'stock_status', 'is_low_stock_display']
    list_filter = [VariantLowStockFilter, 'created_at']
    search_fields = ['product__name', 'product__sku']
    readonly_fields = ['created_at', 'updated_at', 'available_quantity', 'stock_status']
    
    def stock_status(self, obj):
        if obj.quantity == 0:
            return format_html('<span style="color: red; font-weight: bold;">Out of Stock</span>')
        elif obj.is_low_stock:
            return format_html('<span style="color: orange; font-weight: bold;">Low Stock</span>')
        else:
            return format_html('<span style="color: green; font-weight: bold;">In Stock</span>')
    stock_status.short_description = 'Status'
    
    def is_low_stock_display(self, obj):
        return obj.is_low_stock
    is_low_stock_display.short_description = 'Low Stock'
    is_low_stock_display.boolean = True
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')

@admin.register(VariantInventory)
class VariantInventoryAdmin(admin.ModelAdmin):
    list_display = ['variant', 'quantity', 'available_quantity', 'reserved_quantity', 'stock_status', 'is_low_stock_display']
    list_filter = [VariantLowStockFilter, 'created_at']
    search_fields = ['variant__sku', 'variant__product__name']
    readonly_fields = ['created_at', 'updated_at', 'available_quantity', 'stock_status']
    
    def stock_status(self, obj):
        if obj.quantity == 0:
            return format_html('<span style="color: red; font-weight: bold;">Out of Stock</span>')
        elif obj.is_low_stock:
            return format_html('<span style="color: orange; font-weight: bold;">Low Stock</span>')
        else:
            return format_html('<span style="color: green; font-weight: bold;">In Stock</span>')
    stock_status.short_description = 'Status'
    
    def is_low_stock_display(self, obj):
        return obj.is_low_stock
    is_low_stock_display.short_description = 'Low Stock'
    is_low_stock_display.boolean = True
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('variant', 'variant__product')

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'title', 'is_approved', 'created_at']
    list_filter = ['rating', 'is_approved', 'created_at']
    search_fields = ['product__name', 'user__email', 'title']
    list_editable = ['is_approved']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'user')

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'product__name']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product')

# Register remaining models
@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ['product', 'attribute', 'values_display']
    list_filter = ['attribute']
    search_fields = ['product__name', 'attribute__name']
    filter_horizontal = ['values']
    
    def values_display(self, obj):
        return ", ".join([str(value) for value in obj.values.all()])
    values_display.short_description = 'Values'

@admin.register(VariantAttribute)
class VariantAttributeAdmin(admin.ModelAdmin):
    list_display = ['variant', 'attribute_value']
    list_filter = ['attribute_value__attribute']
    search_fields = ['variant__sku', 'attribute_value__value']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('variant', 'attribute_value')