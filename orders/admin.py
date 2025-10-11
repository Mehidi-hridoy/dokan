from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponse
import csv
from .models import Order, OrderItem, BulkOrderOperation
from django.urls import reverse
from django.utils import timezone

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['get_total', 'delivery_status_display']
    fields = ['product', 'quantity', 'price', 'get_total', 'color', 'size', 'weight', 'delivery_status', 'delivery_status_display', 'item_note']

    def delivery_status_display(self, obj):
        status_colors = {
            'pending': '#ffc107',
            'picked_up': '#17a2b8',
            'in_transit': '#6f42c1',
            'out_for_delivery': '#20c997',
            'delivered': '#28a745',
            'failed': '#dc3545',
            'returned': '#e83e8c',
        }
        color = status_colors.get(obj.delivery_status, '#6c757d')
        return format_html(
            f'<span style="display: inline-block; padding: 4px 12px; '
            f'background-color: {color}; color: white; border-radius: 12px; '
            f'font-weight: bold; font-size: 12px;">{obj.get_delivery_status_display().upper()}</span>'
        )
    delivery_status_display.short_description = 'Delivery Status'

class StatusFilter(admin.SimpleListFilter):
    title = 'Order Status'
    parameter_name = 'order_status'

    def lookups(self, request, model_admin):
        return Order.ORDER_STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(order_status=self.value())

class CourierStatusFilter(admin.SimpleListFilter):
    title = 'Courier Status'
    parameter_name = 'courier_status'

    def lookups(self, request, model_admin):
        return Order.COURIER_STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(courier_status=self.value())

class CourierChoiceFilter(admin.SimpleListFilter):
    title = 'Courier Service'
    parameter_name = 'courier_choice'

    def lookups(self, request, model_admin):
        return Order.COURIER_STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(courier_choice=self.value())

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number',
        'customer_name',
        'date_display',
        'customer_info_display',
        'product_info_display',
        'total_price_display',
        'order_status_display',
        'courier_status_display',
        'tracking_info_display',
        'order_note_preview',
        'admin_comment_preview',
        'actions_display',
    ]
    
    list_filter = [
        StatusFilter,
        CourierStatusFilter,
        'courier_choice',
        'delivery_area',
        'city',
        'created_at',
    ]
    
    search_fields = [
        'order_number',
        'user__username',
        'user__email',
        'phone_number',
        'tracking_number',
        'shipping_address',
        'delivery_area',
        'city',
        'zip_code',
    ]
    
    readonly_fields = [
        'order_number',
        'created_at',
        'updated_at',
        'subtotal',
        'total',
        'status_stats',
    ]
    
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'
    actions = [
        'export_orders_csv',
        'mark_as_processed',
        'mark_as_delivered',
        'update_tracking_info',
    ]
    
    list_per_page = 10
    list_max_show_all = 500
    
    fieldsets = (
        ('Order Summary', {
            'fields': ('order_number', 'status_stats', 'user', 'created_at', 'updated_at')
        }),
        ('Order Status', {
            'fields': ('order_status', 'payment_status', 'courier_status')
        }),
        ('Customer Information', {
            'fields': (
                'customer_name',
                'shipping_address',
                'billing_address',
                'phone_number',
                'email',
                'delivery_area',
                'city',
                'zip_code',
            )
        }),
        ('Financial Information', {
            'fields': (
                'subtotal',
                'tax_amount',
                'shipping_cost',
                'discount_amount',
                'total',
            )
        }),
        ('Delivery Information', {
            'fields': (
                'courier_name',
                'courier_choice',
                'tracking_number',
                'estimated_delivery',
            )
        }),
        ('Additional Information', {
            'fields': (
                'order_note',
                'admin_comment',
                'payment_method',
            )
        }),
        ('Timestamps', {
            'fields': (
                'processed_at',
                'delivered_at',
                'cancelled_at',
            ),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('order_items', 'order_items__product')

    def changelist_view(self, request, extra_context=None):
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

    def date_display(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M")
    date_display.short_description = 'Date'

    def customer_info_display(self, obj):
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
        items = obj.order_items.all()[:3]
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
            'pending': '#ffc107',
            'processed': '#17a2b8',
            'on_delivery': '#6f42c1',
            'partial_delivery': '#20c997',
            'delivered': '#28a745',
            'cancelled': '#dc3545',
            'returned': '#e83e8c',
        }
        color = status_colors.get(obj.order_status, '#6c757d')
        return format_html(
            f'<span style="display: inline-block; padding: 4px 12px; '
            f'background-color: {color}; color: white; border-radius: 12px; '
            f'font-weight: bold; font-size: 12px;">{obj.get_order_status_display().upper()}</span>'
        )
    order_status_display.short_description = 'Order Status'

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
        color = {
            'pending': '#ffc107',
            'picked_up': '#17a2b8',
            'in_transit': '#6f42c1',
            'out_for_delivery': '#20c997',
            'delivered': '#28a745',
            'failed': '#dc3545',
            'returned': '#e83e8c',
        }.get(obj.courier_status, '#6c757d')
        icon = status_icons.get(obj.courier_status, '📋')
        return format_html(
            f'<span style="display: inline-block; padding: 4px 12px; '
            f'background-color: {color}; color: white; border-radius: 12px; '
            f'font-weight: bold; font-size: 12px;">{icon} {obj.get_courier_status_display().upper()}</span>'
        )
    courier_status_display.short_description = 'Courier Status'

    def tracking_info_display(self, obj):
        if obj.tracking_number and obj.courier_choice:
            tracking_urls = {
                'pathao': f"https://pathao.com/track/{obj.tracking_number}",
                'red_x': f"https://redx.com.bd/track/{obj.tracking_number}",
                'steadfast': f"https://steadfast.com.bd/track/{obj.tracking_number}",
            }
            tracking_url = tracking_urls.get(obj.courier_choice, '#')
            return format_html(
                f'<a href="{tracking_url}" target="_blank" style="color: #007bff; text-decoration: underline;">'
                f'📍 {obj.tracking_number} ({obj.courier_choice.title()})</a><br>'
                f'<span>Est. Delivery: {obj.estimated_delivery or "N/A"}</span>'
            )
        return format_html('<span>📍 No tracking info</span>')
    tracking_info_display.short_description = 'Tracking Info'

    def order_note_preview(self, obj):
        if obj.order_note:
            preview = obj.order_note[:50] + "..." if len(obj.order_note) > 50 else obj.order_note
            return format_html(f'<span title="{obj.order_note}">📝 {preview}</span>')
        return "—"
    order_note_preview.short_description = 'Order Note'

    def admin_comment_preview(self, obj):
        if obj.admin_comment:
            preview = obj.admin_comment[:50] + "..." if len(obj.admin_comment) > 50 else obj.admin_comment
            return format_html(f'<span title="{obj.admin_comment}">💬 {preview}</span>')
        return "—"
    admin_comment_preview.short_description = 'Comment'

    def actions_display(self, obj):
        tracking_url = '#'
        if obj.tracking_number and obj.courier_choice:
            tracking_urls = {
                'pathao': f"https://pathao.com/track/{obj.tracking_number}",
                'red_x': f"https://redx.com.bd/track/{obj.tracking_number}",
                'steadfast': f"https://steadfast.com.bd/track/{obj.tracking_number}",
            }
            tracking_url = tracking_urls.get(obj.courier_choice, '#')
        
        return format_html(
            f'<div style="display: flex; gap: 5px; flex-wrap: wrap;">'
            f'<a href="/admin/orders/order/{obj.id}/change/" class="button" style="padding: 4px 8px; background: #417690; color: white; text-decoration: none; border-radius: 3px; font-size: 12px;">Edit</a>'
            f'<a href="/admin/orders/order/{obj.id}/delete/" class="button" style="padding: 4px 8px; background: #ba2121; color: white; text-decoration: none; border-radius: 3px; font-size: 12px;">Delete</a>'
            f'<a href="{tracking_url}" target="_blank" class="button" style="padding: 4px 8px; background: #006b1b; color: white; text-decoration: none; border-radius: 3px; font-size: 12px;">Track</a>'
            f'</div>'
        )
    actions_display.short_description = 'Actions'

    def status_stats(self, obj):
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

    def export_orders_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Order Number',
            'Date',
            'Customer',
            'Email',
            'Phone',
            'Total Amount',
            'Order Status',
            'Courier Status',
            'Courier Service',
            'Tracking Number',
            'Estimated Delivery',
            'Delivery Area',
            'City',
            'Zip Code',
            'Products',
        ])
        
        for order in queryset:
            products = "; ".join([f"{item.product.name} (x{item.quantity})" for item in order.order_items.all()])
            writer.writerow([
                order.order_number,
                order.created_at,
                order.customer_name or (order.user.get_full_name() if order.user else 'Guest'),
                order.email,
                order.phone_number,
                order.total,
                order.get_order_status_display(),
                order.get_courier_status_display(),
                order.get_courier_choice_display() or order.courier_name or 'N/A',
                order.tracking_number or 'N/A',
                order.estimated_delivery or 'N/A',
                order.delivery_area or 'N/A',
                order.city or 'N/A',
                order.zip_code or 'N/A',
                products,
            ])
        
        return response
    export_orders_csv.short_description = "Export selected orders to CSV"

    def mark_as_processed(self, request, queryset):
        updated = queryset.update(order_status='processed', processed_at=timezone.now())
        self.message_user(request, f'{updated} orders marked as processed.')
    mark_as_processed.short_description = "Mark selected orders as processed"

    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(
            order_status='delivered',
            courier_status='delivered',
            delivered_at=timezone.now()
        )
        self.message_user(request, f'{updated} orders marked as delivered.')
    mark_as_delivered.short_description = "Mark selected orders as delivered"

    def update_tracking_info(self, request, queryset):
        updated = queryset.update(
            courier_status='in_transit',
            tracking_number=lambda obj: f"TRACK-{obj.order_number}",
            estimated_delivery=timezone.now().date() + timezone.timedelta(days=3)
        )
        self.message_user(request, f'{updated} orders updated with tracking information.')
    update_tracking_info.short_description = "Update tracking information for selected orders"

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
        'delivery_status_display',
        'item_note',
        'actions_display',  # Add actions column
    ]
    
    list_filter = ['order__order_status', 'delivery_status', 'color', 'size', 'created_at']
    search_fields = ['order__order_number', 'product__name', 'tracking_number']
    
    def customer_name(self, obj):
        return obj.order.customer_name or (obj.order.user.get_full_name() if obj.order.user else "Guest")
    customer_name.short_description = 'Customer Name'

    def order_number(self, obj):
        return obj.order.order_number
    order_number.short_description = 'Order Number'
    
    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = 'Product'

    def delivery_status_display(self, obj):
        status_colors = {
            'pending': '#ffc107',
            'picked_up': '#17a2b8',
            'in_transit': '#6f42c1',
            'out_for_delivery': '#20c997',
            'delivered': '#28a745',
            'failed': '#dc3545',
            'returned': '#e83e8c',
        }
        color = status_colors.get(obj.delivery_status, '#6c757d')
        choices = getattr(obj, 'DELIVERY_STATUS_CHOICES', [
            ('pending', 'Pending'),
            ('picked_up', 'Picked Up'),
            ('in_transit', 'In Transit'),
            ('out_for_delivery', 'Out For Delivery'),
            ('delivered', 'Delivered'),
            ('failed', 'Failed'),
            ('returned', 'Returned'),
        ])
        options_html = ""
        current_status = obj.delivery_status
        for value, label in choices:
            selected = 'selected' if value == current_status else ''
            options_html += f'<option value="{value}" {selected}>{label}</option>'
        # Add Save button next to dropdown
        save_url = f"/admin/orders/orderitem/{obj.id}/change/"
        dropdown_html = (
            f'<form method="get" action="{save_url}" style="display:inline;">'
            f'<select name="delivery_status" style="background:{color};color:white;border-radius:12px;padding:4px 12px;font-weight:bold;font-size:12px;">'
            f'{options_html}'
            f'</select>'
            f'<button type="submit" style="margin-left:8px; background:#28a745; color:white; border:none; border-radius:4px; padding:4px 8px; font-size:12px;">Save</button>'
            f'</form>'
        )
        return format_html(dropdown_html)
    delivery_status_display.short_description = 'Delivery Status'

    def actions_display(self, obj):
        # Only show Delete action
        delete_url = f"/admin/orders/orderitem/{obj.id}/delete/"
        return format_html(
            f'<a href="{delete_url}" class="button" style="padding:4px 8px; background:#ba2121; color:white; text-decoration:none; border-radius:3px; font-size:12px;">Delete</a>'
        )
    actions_display.short_description = 'Actions'

@admin.register(BulkOrderOperation)
class BulkOrderOperationAdmin(admin.ModelAdmin):
    list_display = ['name', 'operation_type', 'created_by', 'created_at', 'completed', 'orders_count']
    list_filter = ['operation_type', 'completed', 'created_at']
    filter_horizontal = ['orders_affected']
    
    def orders_count(self, obj):
        return obj.orders_affected.count()
    orders_count.short_description = 'Orders Affected'