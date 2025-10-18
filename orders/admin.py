from django.contrib import admin
from .models import Order, OrderItem, BulkOrderOperation

# Inline for Order Items
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'created_at')
    can_delete = False

# Admin for Orders
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'user', 'customer_name', 'order_status', 'payment_status',
        'courier_status', 'total', 'created_at', 'assigned_staff'
    )
    list_filter = ('order_status', 'payment_status', 'courier_status', 'created_at', 'delivery_area')
    search_fields = ('order_number', 'user__username', 'customer_name', 'email', 'phone_number')
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'processed_at', 'delivered_at', 'cancelled_at', 'total')
    inlines = [OrderItemInline]
    ordering = ('-created_at',)

    # Action to bulk approve orders
    actions = ['approve_orders', 'reject_orders']

    def approve_orders(self, request, queryset):
        updated = queryset.update(order_status='confirmed')
        self.message_user(request, f"{updated} order(s) approved.")
    approve_orders.short_description = "Approve selected orders"

    def reject_orders(self, request, queryset):
        updated = queryset.update(order_status='rejected')
        self.message_user(request, f"{updated} order(s) rejected.")
    reject_orders.short_description = "Reject selected orders"

# Admin for BulkOrderOperation
@admin.register(BulkOrderOperation)
class BulkOrderOperationAdmin(admin.ModelAdmin):
    list_display = ('name', 'operation_type', 'created_by', 'created_at', 'completed')
    list_filter = ('operation_type', 'completed', 'created_at')
    search_fields = ('name', 'created_by__username')
    filter_horizontal = ('orders_affected',)
    readonly_fields = ('created_at',)

