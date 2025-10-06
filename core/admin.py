from django.contrib import admin
from django.contrib.auth.models import Group
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from .models import *

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'first_name', 'last_name', 'user_type', 'is_active', 'date_joined']
    list_filter = ['user_type', 'is_active', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name']
    readonly_fields = ['date_joined', 'last_login']

class InventoryInline(admin.TabularInline):
    model = Inventory
    extra = 1

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'price', 'status', 'inventory_status']
    list_filter = ['status', 'category', 'brand', 'featured']
    search_fields = ['name', 'sku', 'description']
    inlines = [ProductImageInline, InventoryInline]
    readonly_fields = ['created_at', 'updated_at']
    
    def inventory_status(self, obj):
        if hasattr(obj, 'inventory'):
            if obj.inventory.quantity == 0:
                return format_html('<span style="color: red;">Out of Stock</span>')
            elif obj.inventory.quantity <= obj.inventory.low_stock_threshold:
                return format_html('<span style="color: orange;">Low Stock</span>')
            else:
                return format_html('<span style="color: green;">In Stock</span>')
        return 'N/A'

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'product_count', 'is_active']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'description']
    
    def product_count(self, obj):
        return obj.products.count()

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_count', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
    
    def product_count(self, obj):
        return obj.products.count()

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    readonly_fields = ['product', 'quantity', 'unit_price', 'total_price']
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer', 'status', 'payment_status', 'total', 'created_at']
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['order_number', 'customer__email']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    actions = ['mark_as_processing', 'mark_as_shipped']

    def mark_as_processing(self, request, queryset):
        queryset.update(status='processing')
    mark_as_processing.short_description = "Mark selected orders as Processing"

    def mark_as_shipped(self, request, queryset):
        queryset.update(status='shipped')
    mark_as_shipped.short_description = "Mark selected orders as Shipped"

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'coupon_type', 'discount_value', 'start_date', 'end_date', 'is_active', 'usage_count']
    list_filter = ['coupon_type', 'is_active', 'start_date', 'end_date']
    search_fields = ['code', 'description']
    
    def usage_count(self, obj):
        return obj.used_count

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_person', 'email', 'phone', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'contact_person', 'email']

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['po_number', 'supplier', 'status', 'total_amount', 'order_date']
    list_filter = ['status', 'supplier', 'order_date']
    search_fields = ['po_number', 'supplier__name']

@admin.register(LandingPage)
class LandingPageAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}

@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_preview', 'description']
    search_fields = ['key', 'description']
    
    def value_preview(self, obj):
        return obj.value[:50] + '...' if len(obj.value) > 50 else obj.value

# Custom Admin Site
class DokanAdminSite(admin.AdminSite):
    site_header = "Dokan Administration"
    site_title = "Dokan Admin Portal"
    index_title = "Welcome to Dokan Admin Panel"

admin_site = DokanAdminSite(name='dokan_admin')

# Register all models with custom admin site
admin_site.register(User, UserAdmin)
admin_site.register(Product, ProductAdmin)
admin_site.register(Category, CategoryAdmin)
admin_site.register(Brand, BrandAdmin)
admin_site.register(Order, OrderAdmin)
admin_site.register(Coupon, CouponAdmin)
admin_site.register(Supplier, SupplierAdmin)
admin_site.register(PurchaseOrder, PurchaseOrderAdmin)
admin_site.register(LandingPage, LandingPageAdmin)
admin_site.register(SiteSetting, SiteSettingAdmin)