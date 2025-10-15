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

from .models import Order, OrderItem, BulkOrderOperation

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = [
        'product_name', 
        'product_code', 
        'unit_price', 
        'original_unit_price',
        'get_total_display'
    ]
    fields = [
        'product', 
        'product_name', 
        'quantity', 
        'unit_price', 
        'get_total_display',
        'color', 
        'size', 
        'weight'
    ]
    
    def get_total_display(self, obj):
        return f"${obj.get_total()}"
    get_total_display.short_description = 'Total'
    
    def has_add_permission(self, request, obj=None):
        return True
    
    def has_delete_permission(self, request, obj=None):
        return obj and obj.order_status not in ['delivered', 'cancelled']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Card View Display
    list_display = [
        'order_card',
        'customer_info',
        'financial_summary',
        'status_badges',
        'delivery_info',
        'quick_actions'
    ]
    
    list_display_links = None
    list_per_page = 15
    
    # Filters and Search
    list_filter = [
        'order_status',
        'courier_status',
        'payment_status',
        'delivery_area',
        'payment_method',
        'created_at',
        'assigned_staff'
    ]
    
    search_fields = [
        'order_number',
        'customer_name',
        'email',
        'phone_number',
        'customer__name',
        'customer__email',
        'tracking_number'
    ]
    
    # Inline editing
    inlines = [OrderItemInline]
    
    # Fieldsets for detailed view
    fieldsets = (
        ('Order Information', {
            'fields': (
                'order_number',
                'order_status',
                'courier_status',
                'payment_status',
                'payment_method',
                'assigned_staff'
            )
        }),
        ('Customer Information', {
            'fields': (
                'customer',
                'customer_name',
                'email',
                'phone_number',
                'shipping_address',
                'billing_address'
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
                'delivery_area',
                'city',
                'zip_code',
                'courier_choice',
                'courier_name',
                'tracking_number',
                'estimated_delivery'
            )
        }),
        ('Additional Information', {
            'fields': (
                'order_note',
                'admin_comment'
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'processed_at',
                'delivered_at',
                'cancelled_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'order_number', 
        'created_at', 
        'updated_at',
        'subtotal',
        'total'
    ]
    
    # Custom actions
    actions = [
        'mark_as_confirmed',
        'mark_as_processed',
        'mark_as_delivered',
        'mark_as_cancelled',
        'assign_to_staff',
        'update_courier_status',
        'export_orders_csv'
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'customer', 'assigned_staff', 'user'
        ).prefetch_related('order_items')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('quick-actions/<int:order_id>/<str:action>/', 
                 self.admin_site.admin_view(self.handle_quick_action),
                 name='orders_quick_action'),
            path('bulk-status-update/', 
                 self.admin_site.admin_view(self.bulk_status_update_view),
                 name='orders_bulk_status_update'),
            path('order-analytics/', 
                 self.admin_site.admin_view(self.order_analytics_view),
                 name='orders_analytics'),
            path('print-shipping-labels/', 
                 self.admin_site.admin_view(self.print_shipping_labels_view),
                 name='print_shipping_labels'),
        ]
        return custom_urls + urls
    
    # Custom list display methods for card view
    def order_card(self, obj):
        """Display order as a card"""
        # Determine priority color
        if obj.order_status == 'pending':
            priority_color = '#f39c12'
            priority_text = 'New'
        elif obj.order_status in ['confirmed', 'processed']:
            priority_color = '#3498db'
            priority_text = 'Processing'
        elif obj.order_status == 'delivered':
            priority_color = '#27ae60'
            priority_text = 'Completed'
        else:
            priority_color = '#95a5a6'
            priority_text = obj.get_order_status_display()
        
        # Items count
        items_count = obj.order_items.count()
        
        return format_html(
            '''
            <div class="order-card" style="display: flex; align-items: center; gap: 12px; padding: 8px 0;">
                <div style="flex-shrink: 0;">
                    <div style="width: 60px; height: 60px; background: {priority_color}; color: white; 
                         border-radius: 8px; display: flex; flex-direction: column; align-items: center; 
                         justify-content: center; font-weight: bold; text-align: center;">
                        <div style="font-size: 10px; line-height: 1.1;">{priority_text}</div>
                        <div style="font-size: 8px; margin-top: 2px;">{items_count} items</div>
                    </div>
                </div>
                <div style="flex-grow: 1; min-width: 0;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
                        <strong style="font-size: 14px; color: #333; margin: 0; line-height: 1.3;">
                            <a href="{edit_url}" style="text-decoration: none; color: inherit;">{order_number}</a>
                        </strong>
                        <span style="font-size: 12px; color: #666; font-weight: 500;">
                            ${total}
                        </span>
                    </div>
                    <div style="font-size: 12px; color: #666; margin-bottom: 2px;">
                        <strong>Placed:</strong> {created_date}
                    </div>
                    <div style="font-size: 11px; color: #888; line-height: 1.2;">
                        {customer_name}
                    </div>
                </div>
            </div>
            ''',
            priority_color=priority_color,
            priority_text=priority_text,
            items_count=items_count,
            edit_url=f'{obj.id}/change/',
            order_number=obj.order_number,
            total=obj.total,
            created_date=obj.created_at.strftime('%b %d, %Y'),
            customer_name=obj.get_customer_display()
        )
    order_card.short_description = 'Order'
    
    def customer_info(self, obj):
        """Display customer information"""
        customer_html = f'''
            <div style="font-size: 13px; font-weight: 500; color: #2c3e50; margin-bottom: 2px;">
                {obj.get_customer_display()}
            </div>
        '''
        
        contact_html = f'''
            <div style="font-size: 11px; color: #7f8c8d; margin-bottom: 2px;">
                📞 {obj.phone_number or 'No phone'}
            </div>
            <div style="font-size: 11px; color: #7f8c8d;">
                ✉️ {obj.email or 'No email'}
            </div>
        '''
        
        address_html = ''
        if obj.shipping_address:
            short_address = obj.shipping_address[:50] + '...' if len(obj.shipping_address) > 50 else obj.shipping_address
            address_html = f'''
                <div style="font-size: 10px; color: #95a5a6; margin-top: 4px;">
                    🏠 {short_address}
                </div>
            '''
        
        return format_html(customer_html + contact_html + address_html)
    customer_info.short_description = 'Customer'
    
    def financial_summary(self, obj):
        """Display financial summary"""
        items_count = obj.order_items.count()
        
        # Payment status badge
        payment_colors = {
            'paid': '#27ae60',
            'pending': '#f39c12',
            'failed': '#e74c3c',
            'refunded': '#3498db',
            'partially_refunded': '#9b59b6'
        }
        payment_color = payment_colors.get(obj.payment_status, '#95a5a6')
        
        financial_html = f'''
            <div style="text-align: center;">
                <div style="font-size: 16px; font-weight: bold; color: #2c3e50;">
                    ${obj.total}
                </div>
                <div style="font-size: 11px; color: #7f8c8d; margin: 2px 0;">
                    {items_count} item{'' if items_count == 1 else 's'}
                </div>
                <div style="background-color: {payment_color}; color: white; padding: 2px 8px; 
                      border-radius: 12px; font-size: 10px; font-weight: bold; display: inline-block;">
                    {obj.get_payment_status_display()}
                </div>
            </div>
        '''
        
        # Payment method
        if obj.payment_method:
            payment_method_html = f'''
                <div style="font-size: 10px; color: #95a5a6; margin-top: 4px;">
                    {obj.get_payment_method_display()}
                </div>
            '''
        else:
            payment_method_html = '<div style="font-size: 10px; color: #95a5a6;">No method</div>'
        
        return format_html(financial_html + payment_method_html)
    financial_summary.short_description = 'Financial'
    
    def status_badges(self, obj):
        """Display status badges"""
        # Order status badge
        order_colors = {
            'confirmed': '#27ae60',
            'pending': '#f39c12',
            'processed': '#3498db',
            'hold': '#e67e22',
            'rejected': '#e74c3c'
        }
        order_color = order_colors.get(obj.order_status, '#95a5a6')
        
        # Courier status badge
        courier_colors = {
            'delivered': '#27ae60',
            'out_for_delivery': '#3498db',
            'in_transit': '#f39c12',
            'picked_up': '#9b59b6',
            'pending': '#95a5a6',
            'failed': '#e74c3c',
            'returned': '#34495e'
        }
        courier_color = courier_colors.get(obj.courier_status, '#95a5a6')
        
        return format_html(
            '''
            <div style="display: flex; flex-direction: column; gap: 4px;">
                <span style="background-color: {order_color}; color: white; padding: 4px 8px; 
                      border-radius: 12px; font-size: 10px; font-weight: bold; text-align: center;">
                    {order_status}
                </span>
                <span style="background-color: {courier_color}; color: white; padding: 4px 8px; 
                      border-radius: 12px; font-size: 10px; font-weight: bold; text-align: center;">
                    {courier_status}
                </span>
            </div>
            ''',
            order_color=order_color,
            order_status=obj.get_order_status_display(),
            courier_color=courier_color,
            courier_status=obj.get_courier_status_display()
        )
    status_badges.short_description = 'Status'
    
    def delivery_info(self, obj):
        """Display delivery information"""
        delivery_html = f'''
            <div style="font-size: 12px; font-weight: 500; color: #2c3e50; margin-bottom: 2px;">
                {obj.delivery_area or 'No area'}
            </div>
        '''
        
        courier_html = ''
        if obj.courier_choice:
            courier_html = f'''
                <div style="font-size: 11px; color: #7f8c8d; margin-bottom: 2px;">
                    🚚 {obj.get_courier_choice_display()}
                </div>
            '''
        
        tracking_html = ''
        if obj.tracking_number:
            tracking_html = f'''
                <div style="font-size: 10px; color: #3498db; margin-bottom: 2px;">
                    📦 {obj.tracking_number}
                </div>
            '''
        
        eta_html = ''
        if obj.estimated_delivery:
            today = timezone.now().date()
            if obj.estimated_delivery == today:
                eta_text = "Today"
                eta_color = "#27ae60"
            elif obj.estimated_delivery < today:
                eta_text = "Overdue"
                eta_color = "#e74c3c"
            else:
                days_until = (obj.estimated_delivery - today).days
                eta_text = f"In {days_until} days"
                eta_color = "#f39c12"
            
            eta_html = f'''
                <div style="font-size: 10px; color: {eta_color}; font-weight: bold;">
                    ⏰ {eta_text}
                </div>
            '''
        
        return format_html(delivery_html + courier_html + tracking_html + eta_html)
    delivery_info.short_description = 'Delivery'
    
    def quick_actions(self, obj):
        """Display quick action buttons"""
        return format_html(
            '''
            <div class="quick-actions" style="display: flex; flex-direction: column; gap: 4px;">
                <a href="{edit_url}" class="button" style="padding: 4px 8px; background: #3498db; color: white; 
                   text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center;">Edit</a>
                
                <button type="button" onclick="handleOrderAction({order_id}, 'confirm')" 
                        style="padding: 4px 8px; background: #27ae60; color: white; border: none; 
                        border-radius: 4px; font-size: 11px; cursor: pointer; {confirm_style}">
                    Confirm
                </button>
                
                <button type="button" onclick="handleOrderAction({order_id}, 'process')" 
                        style="padding: 4px 8px; background: #f39c12; color: white; border: none; 
                        border-radius: 4px; font-size: 11px; cursor: pointer; {process_style}">
                    Process
                </button>
                
                <button type="button" onclick="handleOrderAction({order_id}, 'deliver')" 
                        style="padding: 4px 8px; background: #2ecc71; color: white; border: none; 
                        border-radius: 4px; font-size: 11px; cursor: pointer; {deliver_style}">
                    Deliver
                </button>
                
                <a href="/admin/orders/order/{order_id}/print-label/" 
                   style="padding: 4px 8px; background: #9b59b6; color: white; text-decoration: none; 
                   border-radius: 4px; font-size: 11px; text-align: center;">
                    Label
                </a>
            </div>
            
            <script>
            function handleOrderAction(orderId, action) {{
                fetch(`/admin/orders/order/quick-actions/${{orderId}}/${{action}}/`, {{
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
            order_id=obj.id,
            confirm_style='display: none;' if obj.order_status != 'pending' else '',
            process_style='display: none;' if obj.order_status != 'confirmed' else '',
            deliver_style='display: none;' if obj.order_status != 'processed' else ''
        )
    quick_actions.short_description = 'Actions'
    
    # Custom Actions
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(order_status='confirmed')
        self.message_user(request, f'{updated} orders confirmed.', messages.SUCCESS)
    mark_as_confirmed.short_description = "Mark selected orders as confirmed"
    
    def mark_as_processed(self, request, queryset):
        updated = queryset.update(order_status='processed', processed_at=timezone.now())
        self.message_user(request, f'{updated} orders processed.', messages.SUCCESS)
    mark_as_processed.short_description = "Mark selected orders as processed"
    
    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(
            order_status='delivered', 
            courier_status='delivered',
            delivered_at=timezone.now()
        )
        self.message_user(request, f'{updated} orders marked as delivered.', messages.SUCCESS)
    mark_as_delivered.short_description = "Mark selected orders as delivered"
    
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(order_status='cancelled', cancelled_at=timezone.now())
        self.message_user(request, f'{updated} orders cancelled.', messages.WARNING)
    mark_as_cancelled.short_description = "Cancel selected orders"
    
    def assign_to_staff(self, request, queryset):
        if 'apply' in request.POST:
            staff_id = request.POST.get('staff')
            if staff_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    staff = User.objects.get(id=staff_id)
                    updated = queryset.update(assigned_staff=staff)
                    self.message_user(request, f'{updated} orders assigned to {staff.username}.', messages.SUCCESS)
                    return redirect(request.get_full_path())
                except User.DoesNotExist:
                    self.message_user(request, 'Staff member not found.', messages.ERROR)
        
        staff_users = get_user_model().objects.filter(is_staff=True)
        return render(request, 'admin/orders/assign_staff.html', {
            'orders': queryset,
            'staff_users': staff_users,
            'action': 'assign_to_staff'
        })
    assign_to_staff.short_description = "Assign to staff member"
    
    def update_courier_status(self, request, queryset):
        if 'apply' in request.POST:
            courier_status = request.POST.get('courier_status')
            tracking_number = request.POST.get('tracking_number', '')
            
            if courier_status:
                update_kwargs = {'courier_status': courier_status}
                if tracking_number:
                    update_kwargs['tracking_number'] = tracking_number
                
                updated = queryset.update(**update_kwargs)
                self.message_user(request, f'{updated} orders courier status updated.', messages.SUCCESS)
                return redirect(request.get_full_path())
        
        return render(request, 'admin/orders/update_courier.html', {
            'orders': queryset,
            'courier_choices': Order.COURIER_STATUS_CHOICES,
            'action': 'update_courier_status'
        })
    update_courier_status.short_description = "Update courier status"
    
    # Quick Actions Handler
    def handle_quick_action(self, request, order_id, action):
        try:
            order = Order.objects.get(id=order_id)
            
            if action == 'confirm' and order.order_status == 'pending':
                order.order_status = 'confirmed'
                order.save()
            elif action == 'process' and order.order_status == 'confirmed':
                order.order_status = 'processed'
                order.processed_at = timezone.now()
                order.save()
            elif action == 'deliver' and order.order_status == 'processed':
                order.order_status = 'delivered'
                order.courier_status = 'delivered'
                order.delivered_at = timezone.now()
                order.save()
            
            return JsonResponse({'success': True})
        
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Order not found'})
    
    # Bulk Status Update View
    def bulk_status_update_view(self, request):
        if request.method == 'POST':
            # Handle bulk status update logic
            pass
        
        recent_orders = Order.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        )[:20]
        
        return render(request, 'admin/orders/bulk_status_update.html', {
            'recent_orders': recent_orders,
            'title': 'Bulk Status Update'
        })
    
    # Order Analytics View
    def order_analytics_view(self, request):
        # Order statistics
        total_orders = Order.objects.count()
        today_orders = Order.objects.filter(
            created_at__date=timezone.now().date()
        ).count()
        
        # Status breakdown
        status_breakdown = Order.objects.values('order_status').annotate(
            count=Count('id')
        ).order_by('order_status')
        
        # Revenue analytics
        total_revenue = Order.objects.aggregate(total=Sum('total'))['total'] or 0
        today_revenue = Order.objects.filter(
            created_at__date=timezone.now().date()
        ).aggregate(total=Sum('total'))['total'] or 0
        
        # Recent orders for display
        recent_orders = Order.objects.select_related('customer').prefetch_related('order_items')[:10]
        
        return render(request, 'admin/orders/order_analytics.html', {
            'total_orders': total_orders,
            'today_orders': today_orders,
            'status_breakdown': status_breakdown,
            'total_revenue': total_revenue,
            'today_revenue': today_revenue,
            'recent_orders': recent_orders,
            'title': 'Order Analytics'
        })
    
    # Print Shipping Labels View
    def print_shipping_labels_view(self, request):
        if request.method == 'POST':
            order_ids = request.POST.getlist('order_ids')
            orders = Order.objects.filter(id__in=order_ids)
            return render(request, 'admin/orders/shipping_labels.html', {
                'orders': orders,
                'title': 'Shipping Labels'
            })
        
        pending_orders = Order.objects.filter(
            order_status__in=['confirmed', 'processed']
        ).select_related('customer')[:50]
        
        return render(request, 'admin/orders/print_labels.html', {
            'pending_orders': pending_orders,
            'title': 'Print Shipping Labels'
        })
    
    @admin.display(description="Ordered Products")
    def ordered_products(self, obj):
        """
        Shows all product names linked to this order.
        """
        products = obj.order_items.all().select_related('product')
        product_list = [item.product.name for item in products]
        return format_html("<br>".join(product_list))

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'item_card',
        'order_info',
        'pricing_info',
        'status_badges',
        'quick_actions'
    ]
    
    list_display_links = None
    list_per_page = 20
    
    list_filter = [
        'order__order_status',
        'order_status',
        'courier_status',
        'created_at'
    ]
    
    search_fields = [
        'order__order_number',
        'product_name',
        'product_code',
        'customer__name'
    ]
    
    readonly_fields = [
        'product_name',
        'product_code',
        'unit_price',
        'original_unit_price',
        'created_at',
        'updated_at'
    ]
    
    def item_card(self, obj):
        """Display order item as a card"""
        return format_html(
            '''
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="flex-shrink: 0;">
                    <div style="width: 50px; height: 50px; background: #ecf0f1; border-radius: 6px; 
                         display: flex; align-items: center; justify-content: center; font-weight: bold; 
                         color: #7f8c8d; font-size: 12px;">
                        {quantity}x
                    </div>
                </div>
                <div style="flex-grow: 1;">
                    <div style="font-size: 13px; font-weight: 500; color: #2c3e50; margin-bottom: 2px;">
                        {product_name}
                    </div>
                    <div style="font-size: 11px; color: #7f8c8d;">
                        Code: {product_code}
                    </div>
                    <div style="font-size: 10px; color: #95a5a6;">
                        {variants}
                    </div>
                </div>
            </div>
            ''',
            quantity=obj.quantity,
            product_name=obj.product_name,
            product_code=obj.product_code,
            variants=self.get_variants_display(obj)
        )
    item_card.short_description = 'Item'
    
    def get_variants_display(self, obj):
        variants = []
        if obj.color:
            variants.append(f"Color: {obj.color}")
        if obj.size:
            variants.append(f"Size: {obj.size}")
        if obj.weight:
            variants.append(f"Weight: {obj.weight}")
        return ', '.join(variants) if variants else 'No variants'
    
    def order_info(self, obj):
        """Display order information"""
        return format_html(
            '''
            <div style="text-align: center;">
                <div style="font-size: 12px; font-weight: 500; color: #3498db; margin-bottom: 2px;">
                    {order_number}
                </div>
                <div style="font-size: 11px; color: #7f8c8d;">
                    {customer_name}
                </div>
                <div style="font-size: 10px; color: #95a5a6;">
                    {created_date}
                </div>
            </div>
            ''',
            order_number=obj.order.order_number,
            customer_name=obj.order.get_customer_display(),
            created_date=obj.created_at.strftime('%b %d, %Y')
        )
    order_info.short_description = 'Order'
    
    def pricing_info(self, obj):
        """Display pricing information"""
        total = obj.get_total()
        
        if obj.promotion_applied and obj.discount_amount > 0:
            pricing_html = f'''
                <div style="text-align: center;">
                    <div style="font-size: 14px; font-weight: bold; color: #2c3e50;">
                        ${total}
                    </div>
                    <div style="font-size: 11px; color: #e74c3c; font-weight: bold;">
                        -${obj.discount_amount} off
                    </div>
                    <div style="font-size: 10px; color: #95a5a6;">
                        ${obj.unit_price} each
                    </div>
                </div>
            '''
        else:
            pricing_html = f'''
                <div style="text-align: center;">
                    <div style="font-size: 14px; font-weight: bold; color: #2c3e50;">
                        ${total}
                    </div>
                    <div style="font-size: 10px; color: #95a5a6;">
                        ${obj.unit_price} each
                    </div>
                </div>
            '''
        
        return format_html(pricing_html)
    pricing_info.short_description = 'Pricing'
    
    def status_badges(self, obj):
        """Display status badges"""
        return format_html(
            '''
            <div style="display: flex; flex-direction: column; gap: 3px; align-items: center;">
                <span style="background-color: #3498db; color: white; padding: 2px 6px; 
                      border-radius: 10px; font-size: 9px; font-weight: bold;">
                    {order_status}
                </span>
                <span style="background-color: #9b59b6; color: white; padding: 2px 6px; 
                      border-radius: 10px; font-size: 9px; font-weight: bold;">
                    {courier_status}
                </span>
            </div>
            ''',
            order_status=obj.get_order_status_display(),
            courier_status=obj.get_courier_status_display()
        )
    status_badges.short_description = 'Status'
    
    def quick_actions(self, obj):
        """Display quick actions"""
        return format_html(
            '''
            <div style="display: flex; flex-direction: column; gap: 3px;">
                <a href="{edit_url}" style="padding: 3px 6px; background: #3498db; color: white; 
                   text-decoration: none; border-radius: 3px; font-size: 10px; text-align: center;">
                    Edit
                </a>
                <a href="{order_url}" style="padding: 3px 6px; background: #2ecc71; color: white; 
                   text-decoration: none; border-radius: 3px; font-size: 10px; text-align: center;">
                    View Order
                </a>
            </div>
            ''',
            edit_url=f'{obj.id}/change/',
            order_url=f'/admin/orders/order/{obj.order.id}/change/'
        )
    quick_actions.short_description = 'Actions'

@admin.register(BulkOrderOperation)
class BulkOrderOperationAdmin(admin.ModelAdmin):
    list_display = ['name', 'operation_type', 'created_by', 'orders_count', 'completed', 'created_at']
    list_filter = ['operation_type', 'completed', 'created_at']
    readonly_fields = ['created_at', 'created_by']
    
    def orders_count(self, obj):
        return obj.orders_affected.count()
    orders_count.short_description = 'Orders Affected'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)