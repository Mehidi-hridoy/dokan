from django.contrib import admin
from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'email', 'phone', 'customer_type',
        'total_orders', 'total_spent', 'status', 'created_at'
    )
    list_filter = ('customer_type', 'is_guest', 'is_fraudulent', 'created_at')
    search_fields = ('name', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at', 'first_order_date', 'last_order_date')
    ordering = ('-created_at',)
    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'name', 'email', 'phone', 'avatar', 'ip_address')
        }),
        ('Customer Classification', {
            'fields': ('customer_type', 'is_guest', 'is_fraudulent')
        }),
        ('Statistics', {
            'fields': ('total_orders', 'total_spent', 'first_order_date', 'last_order_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
