from django.contrib import admin
from django.utils.html import format_html
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity']
    can_delete = False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Simple list view
    list_display = [
        'order_number', 
        'customer_name',
        'simple_status',
        'simple_payment', 
        'total',
        'created_date',
        'quick_actions'
    ]
    
    list_filter = ['order_status', 'payment_status', 'created_at']
    search_fields = ['order_number', 'customer_name', 'phone_number']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    list_per_page = 20
    
    # Remove all complex fieldsets - use simple fields
    fieldsets = (
        ('Quick Update', {
            'fields': ('order_status', 'payment_status', 'admin_comment')
        }),
        ('Customer Info', {
            'fields': ('customer_name', 'phone_number', 'email')
        }),
        ('Shipping', {
            'fields': ('shipping_address', 'delivery_area', 'city')
        }),
    )
    
    def simple_status(self, obj):
        color = {
            'pending': 'orange',
            'confirmed': 'green', 
            'processed': 'blue',
            'hold': 'red',
            'rejected': 'darkred'
        }.get(obj.order_status, 'gray')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_order_status_display()
        )
    simple_status.short_description = 'Status'
    
    def simple_payment(self, obj):
        color = {
            'pending': 'orange',
            'paid': 'green',
            'failed': 'red'
        }.get(obj.payment_status, 'gray')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_payment_status_display()
        )
    simple_payment.short_description = 'Payment'
    
    def created_date(self, obj):
        return obj.created_at.strftime("%b %d, %Y")
    created_date.short_description = 'Date'
    
    def quick_actions(self, obj):
        return format_html(
            '<a href="{}" style="background: #4361ee; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px;">Update</a>',
            f'{obj.id}/change/'
        )
    quick_actions.short_description = 'Action'

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity']
    list_filter = ['order__order_status']