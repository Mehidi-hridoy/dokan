# orders/admin.py

from django.contrib import admin
from django.utils import timezone
from .models import Order,BulkOrderOperation # Assuming OrderItem exists or you'll add it later

# --- Custom Admin Action ---
@admin.action(description='Mark selected orders as processed')
def mark_orders_as_processed(modeladmin, request, queryset):
    """
    Sets the order_status to 'processed' and logs the operation,
    using the customer name for the log message.
    """
    updated_count = 0
    
    for order in queryset:
        # Check if the status needs updating
        if order.order_status != 'processed':
            order.order_status = 'processed'
            order.processed_at = timezone.now()
            order.save(update_fields=['order_status', 'processed_at', 'updated_at'])
            updated_count += 1
            
            # --- Using the Customer Name in the log message ---
            customer_display = order.get_customer_display()
            modeladmin.log_change(
                request, 
                order, 
                f"Status updated to 'processed' via bulk action. Customer: {customer_display}"
            )

    modeladmin.message_user(
        request, 
        f"Successfully marked {updated_count} orders as 'processed'."
    )
    
    # Optional: Log the Bulk Operation in the BulkOrderOperation model
    if updated_count > 0:
        BulkOrderOperation.objects.create(
            name=f"Admin Bulk Processed - {timezone.now().strftime('%Y%m%d%H%M')}",
            operation_type='status_update',
            created_by=request.user,
        ).orders_affected.set(queryset.filter(order_status='processed'))

# --- Order Admin Model ---
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 
        'get_customer_display', # Use the method for display
        'order_status', 
        'courier_status', 
        'total', 
        'created_at', 
        'assigned_staff'
    )
    
    # Fields to search across
    search_fields = (
        'order_number', 
        'customer_name', 
        'phone_number', 
        'email', 
        'delivery_area'
    )
    
    # Filters in the right sidebar
    list_filter = (
        'order_status', 
        'courier_status', 
        'payment_status', 
        'delivery_area', 
        'courier_choice', 
        'created_at'
    )
    
    # Custom actions registration
    actions = [mark_orders_as_processed]
    
    # Optionally: Define fieldsets for a cleaner edit page
    fieldsets = (
        ('Order & Status', {
            'fields': ('order_number', 'order_status', 'courier_status', 'payment_status', 'assigned_staff', 'order_note', 'admin_comment')
        }),
        ('Customer Info', {
            'fields': ('customer', 'customer_name', 'phone_number', 'email', 'shipping_address', 'billing_address')
        }),
        ('Financials', {
            'fields': ('subtotal', 'tax_amount', 'shipping_cost', 'discount_amount', 'total', 'payment_method')
        }),
        ('Delivery Details', {
            'fields': ('delivery_area', 'city', 'zip_code', 'courier_choice', 'courier_name', 'tracking_number', 'estimated_delivery')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'processed_at', 'delivered_at', 'cancelled_at')
        }),
    )
    
    # Make created_at, updated_at read-only
    readonly_fields = ('created_at', 'updated_at', 'order_number')


# Register the BulkOrderOperation (optional, but good practice)
@admin.register(BulkOrderOperation)
class BulkOrderOperationAdmin(admin.ModelAdmin):
    list_display = ('name', 'operation_type', 'created_by', 'created_at', 'completed')
    list_filter = ('operation_type', 'completed', 'created_at')
    readonly_fields = ('created_by', 'created_at', 'filters_applied')