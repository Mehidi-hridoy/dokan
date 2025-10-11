from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponse
import csv
from .models import Order, OrderItem, BulkOrderOperation

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['get_total', ]
    fields = ['product', 'quantity', 'price', 'get_total', 'color', 'size', 'weight',]

class StatusFilter(admin.SimpleListFilter):
    title = 'Order Status'
    parameter_name = 'order_status'

    def lookups(self, request, model_admin):
        return [
            ('pending', 'Pending Order'),
            ('processed', 'Processed Order'),
            ('on_delivery', 'On Delivery'),
            ('partial_delivery', 'Partial Delivery'),
            ('delivered', 'Delivered Orders'),
            ('cancelled', 'Cancelled Orders'),
            ('returned', 'Return Orders'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(order_status=self.value())

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Display fields in list view
    list_display = [
        'order_number',
        'customer_name',
        'date_display',
        'customer_info_display',
        'product_info_display',
        'total_price_display',
        'order_status_display',
        'order_note_preview',
        'courier_status_display',
        'admin_comment_preview',
        'actions_display'
    ]
    
    list_filter = [
        StatusFilter,
        'courier_status',
        'delivery_area',
        'created_at',
    ]
    
    search_fields = [
        'order_number',
        'user__username',
        'user__email',
        'phone_number',
        'tracking_number',
        'shipping_address',
    ]
    
    readonly_fields = [
        'order_number', 
        'created_at', 
        'updated_at',
        'subtotal',
        'total',
        'status_stats'
    ]
    
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'
    actions = ['export_orders_csv', 'mark_as_processed', 'mark_as_delivered']
    
    # Pagination settings
    list_per_page = 10
    list_max_show_all = 500
    
    fieldsets = (
        ('Order Summary', {
            'fields': ('order_number', 'status_stats', 'user', 'created_at')
        }),
        ('Order Status', {
            'fields': ('order_status', 'payment_status', 'courier_status')
        }),
        ('Customer Information', {
            'fields': (
                'shipping_address', 
                'billing_address', 
                'phone_number', 
                'email',
                'delivery_area',
                'city',
                'zip_code'
            )
        }),
        ('Financial Information', {
            'fields': (
                'subtotal', 
                'tax_amount', 
                'shipping_cost', 
                'discount_amount', 
                'total'
            )
        }),
        ('Delivery Information', {
            'fields': (
                'courier_name', 
                'tracking_number', 
                'estimated_delivery'
            )
        }),
        ('Additional Information', {
            'fields': (
                'order_note', 
                'admin_comment', 
                'payment_method'
            )
        }),
        ('Timestamps', {
            'fields': (
                'processed_at', 
                'delivered_at',
                'cancelled_at'
            ),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Prefetch related objects for performance
        return queryset.prefetch_related('order_items', 'order_items__product')

    def changelist_view(self, request, extra_context=None):
        # Add statistics to context
        if extra_context is None:
            extra_context = {}
        
        queryset = self.get_queryset(request)
        extra_context['stats'] = {
            'total_orders': queryset.count(),
            'pending_orders': queryset.filter(order_status='pending').count(),
            'processed_orders': queryset.filter(order_status='processed').count(),
            'on_delivery_orders': queryset.filter(order_status='on_delivery').count(),
            'partial_delivery_orders': queryset.filter(order_status='partial_delivery').count(),
            'delivered_orders': queryset.filter(order_status='delivered').count(),
            'cancelled_orders': queryset.filter(order_status='cancelled').count(),
            'returned_orders': queryset.filter(order_status='returned').count(),
        }
        
        return super().changelist_view(request, extra_context=extra_context)

    # Custom display methods for list view
    def date_display(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M")
    date_display.short_description = 'Date'

    def customer_info_display(self, obj):
        # Show the entered customer name first, fallback to user
        name = obj.customer_name or (obj.user.get_full_name() if obj.user else 'Guest')
        phone = obj.phone_number or "No Phone"
        email = obj.email or (obj.user.email if obj.user else "No Email")
        return format_html(
            f"<strong>{name}</strong><br>"
            f"📞 {phone}<br>"
            f"📧 {email}<br>"
            f"📍 {obj.delivery_area or 'N/A'}"
        )
    customer_info_display.short_description = 'Customer Info'


    def product_info_display(self, obj):
        items = obj.order_items.all()[:3]  # Show first 3 items
        product_list = []
        for item in items:
            product_list.append(f"• {item.product.name} (×{item.quantity})")
        
        if obj.order_items.count() > 3:
            product_list.append(f"... +{obj.order_items.count() - 3} more")
        
        return format_html("<br>".join(product_list))
    product_info_display.short_description = 'Product Info'

    def total_price_display(self, obj):
        return format_html(f"<strong>${obj.total}</strong>")
    total_price_display.short_description = 'Total Price'

    def order_status_display(self, obj):
        status_colors = {
            'pending': '#ffc107',      # Orange
            'processed': '#17a2b8',    # Blue
            'on_delivery': '#6f42c1',  # Purple
            'partial_delivery': '#20c997', # Teal
            'delivered': '#28a745',    # Green
            'cancelled': '#dc3545',    # Red
            'returned': '#e83e8c',     # Pink
        }
        color = status_colors.get(obj.order_status, '#6c757d')
        return format_html(
            f'<span style="display: inline-block; padding: 4px 12px; '
            f'background-color: {color}; color: white; border-radius: 12px; '
            f'font-weight: bold; font-size: 12px;">{obj.get_order_status_display().upper()}</span>'
        )
    order_status_display.short_description = 'Order Status'

    def order_note_preview(self, obj):
        if obj.order_note:
            preview = obj.order_note[:50] + "..." if len(obj.order_note) > 50 else obj.order_note
            return format_html(f'<span title="{obj.order_note}">📝 {preview}</span>')
        return "—"
    order_note_preview.short_description = 'Order Note'

    def courier_status_display(self, obj):
        status_icons = {
            'pending': '⏳',
            'picked_up': '📦',
            'in_transit': '🚚',
            'out_for_delivery': '🏍️',
            'delivered': '✅',
            'failed': '❌',
            'returned': '↩️',
        }
        icon = status_icons.get(obj.courier_status, '📋')
        return format_html(f'{icon} {obj.get_courier_status_display()}')
    courier_status_display.short_description = 'Courier Status'

    def admin_comment_preview(self, obj):
        if obj.admin_comment:
            preview = obj.admin_comment[:50] + "..." if len(obj.admin_comment) > 50 else obj.admin_comment
            return format_html(f'<span title="{obj.admin_comment}">💬 {preview}</span>')
        return "—"
    admin_comment_preview.short_description = 'Comment'

    def actions_display(self, obj):
        return format_html(
            f'<div style="display: flex; gap: 5px; flex-wrap: wrap;">'
            f'<a href="/admin/orders/order/{obj.id}/change/" class="button" style="padding: 4px 8px; background: #417690; color: white; text-decoration: none; border-radius: 3px; font-size: 12px;">Edit</a>'
            f'<a href="/admin/orders/order/{obj.id}/delete/" class="button" style="padding: 4px 8px; background: #ba2121; color: white; text-decoration: none; border-radius: 3px; font-size: 12px;">Delete</a>'
            f'<a href="#" class="button" style="padding: 4px 8px; background: #006b1b; color: white; text-decoration: none; border-radius: 3px; font-size: 12px;">Track</a>'
            f'</div>'
        )
    actions_display.short_description = 'Actions'

    def status_stats(self, obj):
        """Display status statistics in the change form"""
        stats = {
            'total': Order.objects.count(),
            'pending': Order.objects.filter(order_status='pending').count(),
            'processed': Order.objects.filter(order_status='processed').count(),
            'on_delivery': Order.objects.filter(order_status='on_delivery').count(),
            'partial_delivery': Order.objects.filter(order_status='partial_delivery').count(),
            'delivered': Order.objects.filter(order_status='delivered').count(),
            'cancelled': Order.objects.filter(order_status='cancelled').count(),
            'returned': Order.objects.filter(order_status='returned').count(),
        }
        
        stats_html = """
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 10px 0;">
        """
        for key, value in stats.items():
            color = {
                'total': '#333',
                'pending': '#ffc107',
                'processed': '#17a2b8',
                'on_delivery': '#6f42c1',
                'partial_delivery': '#20c997',
                'delivered': '#28a745',
                'cancelled': '#dc3545',
                'returned': '#e83e8c',
            }.get(key, '#6c757d')
            
            stats_html += f"""
            <div style="text-align: center; padding: 10px; background: {color}; color: white; border-radius: 5px;">
                <div style="font-size: 18px; font-weight: bold;">{value}</div>
                <div style="font-size: 12px; text-transform: capitalize;">{key.replace('_', ' ')}</div>
            </div>
            """
        stats_html += "</div>"
        return format_html(stats_html)
    status_stats.short_description = 'Order Statistics'

    # Admin actions
    def export_orders_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Order Number', 'Date', 'Customer', 'Email', 'Phone', 
            'Total Amount', 'Order Status', 'Courier Status', 'Delivery Area'
        ])
        
        for order in queryset:
            writer.writerow([
                order.order_number,
                order.created_at,
                order.user.username if order.user else 'Guest',
                order.email,
                order.phone_number,
                order.total,
                order.get_order_status_display(),
                order.get_courier_status_display(),
                order.delivery_area
            ])
        
        return response
    export_orders_csv.short_description = "Export selected orders to CSV"

    def mark_as_processed(self, request, queryset):
        updated = queryset.update(order_status='processed')
        self.message_user(request, f'{updated} orders marked as processed.')
    mark_as_processed.short_description = "Mark selected orders as processed"

    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(order_status='delivered', courier_status='delivered')
        self.message_user(request, f'{updated} orders marked as delivered.')
    mark_as_delivered.short_description = "Mark selected orders as delivered"

    # Pagination controls
    def get_list_per_page(self, request):
        """Allow different pagination sizes"""
        per_page = request.GET.get('per_page')
        if per_page and per_page.isdigit():
            return int(per_page)
        return self.list_per_page

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'order_number',
        'customer_name',
        'product_name',
        'quantity',
        'price',
        'get_total',
        'color',
        'size',
        'weight',
        'item_note',
    ]
    
    list_filter = ['order__order_status', 'created_at', 'color', 'size']
    search_fields = ['order__order_number', 'product__name']
     
    def customer_name(self, obj):
        return obj.order.customer_name or (obj.order.user.get_full_name() if obj.order.user else "Guest")
    customer_name.short_description = 'Customer Name'

    def order_number(self, obj):
        return obj.order.order_number
    order_number.short_description = 'Order Number'
    
    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = 'Product'


@admin.register(BulkOrderOperation)
class BulkOrderOperationAdmin(admin.ModelAdmin):
    list_display = ['name', 'operation_type', 'created_by', 'created_at', 'completed', 'orders_count']
    list_filter = ['operation_type', 'completed', 'created_at']
    filter_horizontal = ['orders_affected']
    
    def orders_count(self, obj):
        return obj.orders_affected.count()
    orders_count.short_description = 'Orders Affected'

# Custom admin template to add pagination controls
class CustomOrderAdmin(OrderAdmin):
    def pagination(self, request):
        """Custom pagination controls"""
        per_page_options = [10, 20, 50, 100, 500]
        current_per_page = self.get_list_per_page(request)
        
        links = []
        for option in per_page_options:
            if option == current_per_page:
                links.append(f'<strong>{option} per page</strong>')
            else:
                links.append(f'<a href="?per_page={option}">{option} per page</a>')
        
        return format_html(' &nbsp; '.join(links))
