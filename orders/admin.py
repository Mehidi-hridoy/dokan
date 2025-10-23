# orders/admin.py
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import path
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.template.response import TemplateResponse
from django.db import models
from .models import Order, OrderItem, BulkOrderOperation

User = get_user_model()

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj):
        return False

class QuickOrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'customer_display', 'order_status_badge', 
        'payment_status_badge', 'courier_status_badge', 'total',
        'created_at', 'quick_actions'
    ]
    list_filter = [
        'order_status', 'payment_status', 'courier_status', 
        'delivery_area', 'created_at', 'assigned_staff'
    ]
    search_fields = [
        'order_number', 'customer_name', 'phone_number', 
        'email', 'tracking_number'
    ]
    readonly_fields = [
        'order_number', 'created_at', 'updated_at', 
        'profit_calculation', 'staff_permission_message'
    ]
    list_per_page = 25
    inlines = [OrderItemInline]
    actions = [
        'confirm_orders', 'hold_orders', 'reject_orders',
        'mark_paid', 'mark_delivered', 'assign_to_me',
        'export_orders', 'quick_status_update'
    ]
    
    fieldsets = (
        ('Permission Info', {
            'fields': ('staff_permission_message',)
        }),
        ('Order Information', {
            'fields': (
                'order_number', 'user', 'assigned_staff',
                'order_status', 'payment_status', 'courier_status'
            )
        }),
        ('Financial Details', {
            'fields': (
                'subtotal', 'tax_amount', 'shipping_cost', 
                'discount_amount', 'total', 'profit_calculation'
            )
        }),
        ('Customer Information', {
            'fields': (
                'customer_name', 'phone_number', 'email',
                'shipping_address', 'billing_address'
            )
        }),
        ('Delivery Details', {
            'fields': (
                'delivery_area', 'city', 'zip_code',
                'courier_name', 'courier_choice', 'tracking_number',
                'estimated_delivery'
            )
        }),
        ('Additional Information', {
            'fields': ('order_note', 'admin_comment', 'payment_method'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'processed_at', 'delivered_at'),
            'classes': ('collapse',)
        }),
    )
    
    def customer_display(self, obj):
        return obj.get_customer_display()
    customer_display.short_description = 'Customer'
    
    def order_status_badge(self, obj):
        colors = {
            'confirmed': 'green',
            'rejected': 'red', 
            'hold': 'orange',
            'pending': 'blue',
            'processed': 'purple'
        }
        color = colors.get(obj.order_status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            color, obj.get_order_status_display()
        )
    order_status_badge.short_description = 'Status'
    
    def payment_status_badge(self, obj):
        colors = {
            'paid': 'green',
            'pending': 'orange',
            'failed': 'red',
            'refunded': 'blue'
        }
        color = colors.get(obj.payment_status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            color, obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Payment'
    
    def courier_status_badge(self, obj):
        colors = {
            'delivered': 'green',
            'in_transit': 'blue',
            'out_for_delivery': 'orange',
            'pending': 'gray'
        }
        color = colors.get(obj.courier_status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">{}</span>',
            color, obj.get_courier_status_display()
        )
    courier_status_badge.short_description = 'Courier'
    
    def quick_actions(self, obj):
        buttons = []
        
        # Status update buttons
        if obj.order_status != 'confirmed':
            buttons.append(
                f'<a href="../{obj.id}/confirm/" class="button" style="background: #28a745; color: white; padding: 2px 6px; text-decoration: none; border-radius: 3px; font-size: 11px;">Confirm</a>'
            )
        
        if obj.order_status != 'processed':
            buttons.append(
                f'<a href="../{obj.id}/process/" class="button" style="background: #007bff; color: white; padding: 2px 6px; text-decoration: none; border-radius: 3px; font-size: 11px;">Process</a>'
            )
        
        buttons.append(
            f'<a href="../{obj.id}/change/" class="button" style="background: #6c757d; color: white; padding: 2px 6px; text-decoration: none; border-radius: 3px; font-size: 11px;">Edit</a>'
        )
        
        return format_html(' '.join(buttons))
    quick_actions.short_description = 'Actions'
    
    def profit_calculation(self, obj):
        """Calculate profit for the order"""
        total_cost = 0
        for item in obj.items.all():
            if item.product and item.product.cost_price:
                total_cost += item.product.cost_price * item.quantity
        
        if total_cost > 0:
            from decimal import Decimal
            profit = obj.total - Decimal(total_cost)
            profit_margin = (profit / obj.total) * 100 if obj.total > 0 else 0
            color = 'green' if profit > 0 else 'red'
            return format_html(
                '''
                <div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">
                    <strong>Total Cost:</strong> ${:.2f}<br>
                    <strong>Profit:</strong> <span style="color: {};">${:.2f}</span><br>
                    <strong>Margin:</strong> <span style="color: {};">{:.1f}%</span>
                </div>
                ''',
                total_cost, color, profit, color, profit_margin
            )
        return "Cost data not available for all products"
    profit_calculation.short_description = 'Profit Analysis'
    
    def staff_permission_message(self, obj):
        assigned_info = ""
        if obj.assigned_staff:
            assigned_info = f"<br><small>Currently assigned to: <strong>{obj.assigned_staff.get_full_name() or obj.assigned_staff.username}</strong></small>"
        
        return format_html(
            '<div style="background: #d4edda; color: #155724; padding: 10px; border-radius: 5px; border: 1px solid #c3e6cb;">'
            '<strong>👨‍💼 Staff Permissions:</strong> You can update order status and information. '
            'Only administrators can delete orders.{}'
            '</div>',
            assigned_info
        )
    staff_permission_message.short_description = 'Permission Info'
    
    # Custom actions
    def confirm_orders(self, request, queryset):
        updated = queryset.update(order_status='confirmed')
        self.message_user(request, f'{updated} orders confirmed.')
    confirm_orders.short_description = "Confirm selected orders"
    
    def hold_orders(self, request, queryset):
        updated = queryset.update(order_status='hold')
        self.message_user(request, f'{updated} orders put on hold.')
    hold_orders.short_description = "Put selected orders on hold"
    
    def reject_orders(self, request, queryset):
        updated = queryset.update(order_status='rejected')
        self.message_user(request, f'{updated} orders rejected.')
    reject_orders.short_description = "Reject selected orders"
    
    def mark_paid(self, request, queryset):
        updated = queryset.update(payment_status='paid')
        self.message_user(request, f'{updated} orders marked as paid.')
    mark_paid.short_description = "Mark selected orders as paid"
    
    def mark_delivered(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            courier_status='delivered', 
            delivered_at=timezone.now()
        )
        self.message_user(request, f'{updated} orders marked as delivered.')
    mark_delivered.short_description = "Mark selected orders as delivered"
    
    def assign_to_me(self, request, queryset):
        updated = queryset.update(assigned_staff=request.user)
        self.message_user(request, f'{updated} orders assigned to you.')
    assign_to_me.short_description = "Assign selected orders to me"
    
    def quick_status_update(self, request, queryset):
        """Quick status update for multiple orders"""
        if 'apply' in request.POST:
            status_type = request.POST.get('status_type')
            new_status = request.POST.get('new_status')
            
            if status_type == 'order_status':
                updated = queryset.update(order_status=new_status)
            elif status_type == 'payment_status':
                updated = queryset.update(payment_status=new_status)
            elif status_type == 'courier_status':
                updated = queryset.update(courier_status=new_status)
                if new_status == 'delivered':
                    from django.utils import timezone
                    queryset.update(delivered_at=timezone.now())
            
            self.message_user(request, f'Updated {updated} orders.')
            return HttpResponseRedirect(request.get_full_path())
        
        from django import forms
        class StatusUpdateForm(forms.Form):
            status_type = forms.ChoiceField(
                choices=[
                    ('order_status', 'Order Status'),
                    ('payment_status', 'Payment Status'), 
                    ('courier_status', 'Courier Status')
                ],
                initial='order_status'
            )
            new_status = forms.ChoiceField(choices=[])
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # Dynamic choices based on status type
                if 'status_type' in self.data:
                    status_type = self.data['status_type']
                    if status_type == 'order_status':
                        self.fields['new_status'].choices = Order.ORDER_STATUS_CHOICES
                    elif status_type == 'payment_status':
                        self.fields['new_status'].choices = Order.PAYMENT_STATUS_CHOICES
                    elif status_type == 'courier_status':
                        self.fields['new_status'].choices = Order.COURIER_STATUS_CHOICES
        
        context = {
            'orders': queryset,
            'form': StatusUpdateForm(),
            'action': 'quick_status_update',
            'title': 'Quick Status Update'
        }
        return admin.views.decorators.staff_member_required(
            lambda request: TemplateResponse(
                request,
                'admin/orders/order/quick_status_update.html',
                context
            )
        )(request)
    quick_status_update.short_description = "Quick status update for selected orders"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/confirm/',
                self.admin_site.admin_view(self.confirm_order),
                name='orders_order_confirm',
            ),
            path(
                '<path:object_id>/process/',
                self.admin_site.admin_view(self.process_order),
                name='orders_order_process',
            ),
            path(
                'quick-create/',
                self.admin_site.admin_view(self.quick_create_view),
                name='orders_order_quick_create',
            ),
        ]
        return custom_urls + urls
    
    def confirm_order(self, request, object_id):
        order = Order.objects.get(pk=object_id)
        order.order_status = 'confirmed'
        order.assigned_staff = request.user  # Auto-assign to confirming staff
        order.save()
        messages.success(request, f'Order {order.order_number} confirmed successfully!')
        return HttpResponseRedirect('../../')
    
    def process_order(self, request, object_id):
        from django.utils import timezone
        order = Order.objects.get(pk=object_id)
        order.order_status = 'processed'
        order.processed_at = timezone.now()
        order.assigned_staff = request.user  # Auto-assign to processing staff
        order.save()
        messages.success(request, f'Order {order.order_number} processed successfully!')
        return HttpResponseRedirect('../../')
    
    def quick_create_view(self, request):
        """Quick order creation for staff"""
        if request.method == 'POST':
            try:
                from decimal import Decimal
                # Create order with minimal data
                order = Order.objects.create(
                    customer_name=request.POST.get('customer_name'),
                    phone_number=request.POST.get('phone_number'),
                    shipping_address=request.POST.get('shipping_address'),
                    delivery_area=request.POST.get('delivery_area'),
                    subtotal=Decimal(request.POST.get('subtotal', 0)),
                    total=Decimal(request.POST.get('total', 0)),
                    payment_method=request.POST.get('payment_method', 'cod'),
                    assigned_staff=request.user  # Auto-assign to creating staff
                )
                messages.success(request, f'Order {order.order_number} created successfully!')
                return HttpResponseRedirect(f'../{order.pk}/change/')
            except Exception as e:
                messages.error(request, f'Error creating order: {str(e)}')
        
        # Simple form for quick order creation
        from django import forms
        class QuickOrderForm(forms.Form):
            customer_name = forms.CharField(max_length=100, required=True)
            phone_number = forms.CharField(max_length=15, required=True)
            shipping_address = forms.CharField(widget=forms.Textarea, required=True)
            delivery_area = forms.CharField(max_length=100, required=True)
            subtotal = forms.DecimalField(max_digits=10, decimal_places=2, required=True)
            total = forms.DecimalField(max_digits=10, decimal_places=2, required=True)
            payment_method = forms.ChoiceField(choices=Order.PAYMENT_METHOD_CHOICES, initial='cod')
        
        context = {
            'form': QuickOrderForm(),
            'title': 'Quick Create Order',
            'opts': self.model._meta,
        }
        return admin.views.decorators.staff_member_required(
            lambda request: TemplateResponse(
                request, 
                'admin/orders/order/quick_create.html', 
                context
            )
        )(request)
    
    # Permission controls for Google OAuth staff
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Staff can change orders assigned to them or unassigned orders"""
        if request.user.is_superuser:
            return True
        if obj and hasattr(obj, 'assigned_staff'):
            return obj.assigned_staff == request.user or obj.assigned_staff is None
        return True
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Staff can see orders assigned to them or unassigned orders
        return qs.filter(models.Q(assigned_staff=request.user) | models.Q(assigned_staff__isnull=True))
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # For staff users, limit assigned_staff field to themselves only
        if not request.user.is_superuser and 'assigned_staff' in form.base_fields:
            form.base_fields['assigned_staff'].queryset = User.objects.filter(id=request.user.id)
            form.base_fields['assigned_staff'].initial = request.user
        return form

admin.site.register(Order, QuickOrderAdmin)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'created_at']
    list_filter = ['order__order_status', 'created_at']
    search_fields = ['order__order_number', 'product__products_name']
    readonly_fields = ['created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(BulkOrderOperation)
class BulkOrderOperationAdmin(admin.ModelAdmin):
    list_display = ['name', 'operation_type', 'created_by', 'created_at', 'completed']
    list_filter = ['operation_type', 'completed', 'created_at']
    readonly_fields = ['created_by', 'created_at', 'filters_applied']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser