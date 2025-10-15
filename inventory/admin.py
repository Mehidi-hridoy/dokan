
from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Inventory, StockMovement, StockAlert

# Inline for StockMovement inside Inventory
class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    readonly_fields = ('previous_quantity', 'new_quantity', 'created_at', 'created_by')
    can_delete = False
    fields = ('movement_type', 'quantity', 'reference', 'note', 'previous_quantity', 'new_quantity', 'created_at', 'created_by')
    
    def has_add_permission(self, request, obj=None):
        """Prevent adding stock movements directly from inventory if stock is out"""
        if obj and obj.is_stock_out:
            return False
        return True

# Inline for StockAlert inside Inventory
class StockAlertInline(admin.TabularInline):
    model = StockAlert
    extra = 0
    readonly_fields = ('status', 'created_at', 'resolved_at')
    can_delete = False
    fields = ('alert_type', 'message', 'status', 'created_at', 'resolved_at')


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        'product_card',
        'stock_info',
        'movement_summary',
        'location_info',
        'status_badges',
        'quick_actions'
    )
    
    list_display_links = None
    list_per_page = 20
    
    list_filter = ('location', 'product__category', 'product__brand')
    search_fields = ('product__products_name', 'product__product_code')
    
    readonly_fields = (
        'last_restocked', 
        'last_updated', 
        'available_quantity', 
        'is_low_stock', 
        'is_stock_out', 
        'needs_restock',
        'total_stock_in', 
        'total_stock_out'
    )
    
    inlines = [StockAlertInline]
    
    # Fieldsets for detailed view
    fieldsets = (
        ('Product Information', {
            'fields': (
                'product',
                'location',
            )
        }),
        ('Stock Information', {
            'fields': (
                'quantity',
                'reserved_quantity',
                'available_quantity',
                'low_stock_threshold',
                'reorder_quantity',
            )
        }),
        ('Status Indicators', {
            'fields': (
                'is_stock_out',
                'is_low_stock',
                'needs_restock',
            ),
            'classes': ('collapse',)
        }),
        ('Restock Information', {
            'fields': (
                'last_restocked',
                'last_updated',
            ),
            'classes': ('collapse',)
        }),
    )
    
    # Custom actions
    actions = [
        'restock_inventory',
        'adjust_low_stock_threshold',
        'clear_reserved_quantities',
        'generate_stock_alerts',
        'export_inventory_report'
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:inventory_id>/add-stock/', 
                 self.admin_site.admin_view(self.add_stock_view),
                 name='inventory_add_stock'),
            path('<int:inventory_id>/adjust-stock/', 
                 self.admin_site.admin_view(self.adjust_stock_view),
                 name='inventory_adjust_stock'),
            path('<int:inventory_id>/quick-restock/', 
                 self.admin_site.admin_view(self.quick_restock),
                 name='inventory_quick_restock'),
            path('bulk-add-stock/', 
                 self.admin_site.admin_view(self.bulk_add_stock_view),
                 name='inventory_bulk_add_stock'),
        ]
        return custom_urls + urls
    
    def get_readonly_fields(self, request, obj=None):
        """Make quantity fields read-only for out of stock items for non-superusers"""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_stock_out and not request.user.is_superuser:
            # Non-superusers cannot modify out of stock items
            readonly_fields.extend(['quantity', 'reserved_quantity'])
        return readonly_fields
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form based on stock status and user permissions"""
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.is_stock_out:
            if not request.user.is_superuser:
                # Add help text for non-superusers
                form.base_fields['quantity'].help_text = "❌ OUT OF STOCK - Only superusers can update stock"
                form.base_fields['reserved_quantity'].help_text = "❌ OUT OF STOCK - Only superusers can update reserved quantity"
            else:
                # Superusers can update with warning
                form.base_fields['quantity'].help_text = "⚠️ OUT OF STOCK - Superuser override enabled"
                form.base_fields['reserved_quantity'].help_text = "⚠️ OUT OF STOCK - Superuser override enabled"
        return form
    
    def has_change_permission(self, request, obj=None):
        """Check if user has permission to change inventory"""
        if obj and obj.is_stock_out and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """Allow superusers to delete inventory, block others"""
        if request.user.is_superuser:
            return True
        return False

    
    # Custom list display methods for card view
    def product_card(self, obj):
        """Display product as a card"""
        product = obj.product
        image_url = product.products_image.url if product.products_image else '/static/admin/img/icon-image.svg'
        
        return format_html(
            '''
            <div class="inventory-card" style="display: flex; align-items: center; gap: 12px; padding: 8px 0;">
                <div style="flex-shrink: 0;">
                    <img src="{image_url}" alt="{name}" 
                         style="width: 60px; height: 60px; object-fit: cover; border-radius: 8px; border: 1px solid #e0e0e0;">
                </div>
                <div style="flex-grow: 1; min-width: 0;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
                        <strong style="font-size: 14px; color: #333; margin: 0; line-height: 1.3;">
                            <a href="{edit_url}" style="text-decoration: none; color: inherit;">{name}</a>
                        </strong>
                    </div>
                    <div style="font-size: 12px; color: #666; margin-bottom: 2px;">
                        <strong>Code:</strong> {code}
                    </div>
                    <div style="font-size: 11px; color: #7f8c8d; line-height: 1.2;">
                        {category}
                    </div>
                </div>
            </div>
            ''',
            image_url=image_url,
            name=product.products_name,
            edit_url=f'{obj.id}/change/',
            code=product.product_code,
            category=product.category.name if product.category else 'No Category'
        )
    product_card.short_description = 'Product'
    
    def stock_info(self, obj):
        """Display stock information"""
        # Stock status color
        if obj.is_stock_out:
            status_color = '#e74c3c'
            status_text = 'OUT OF STOCK'
            status_icon = '❌'
        elif obj.is_low_stock:
            status_color = '#f39c12'
            status_text = 'LOW STOCK'
            status_icon = '⚠️'
        else:
            status_color = '#27ae60'
            status_text = 'IN STOCK'
            status_icon = '✅'
        
        stock_html = f'''
            <div style="text-align: center;">
                <div style="font-size: 18px; font-weight: bold; color: {status_color}; margin-bottom: 4px;">
                    {obj.available_quantity}
                </div>
                <div style="background-color: {status_color}; color: white; padding: 4px 8px; 
                      border-radius: 12px; font-size: 10px; font-weight: bold; display: inline-block;">
                    {status_icon} {status_text}
                </div>
            </div>
        '''
        
        # Reserved quantity info
        if obj.reserved_quantity > 0:
            reserved_html = f'''
                <div style="font-size: 11px; color: #3498db; margin-top: 4px;">
                    📦 {obj.reserved_quantity} reserved
                </div>
            '''
        else:
            reserved_html = '<div style="font-size: 11px; color: #95a5a6;">No reservations</div>'
        
        return format_html(stock_html + reserved_html)
    stock_info.short_description = 'Stock Status'
    
    def movement_summary(self, obj):
        """Display movement summary"""
        total_in = self.total_stock_in(obj)
        total_out = self.total_stock_out(obj)
        
        movement_html = f'''
            <div style="text-align: center;">
                <div style="display: flex; justify-content: space-around; margin-bottom: 4px;">
                    <div>
                        <div style="font-size: 12px; color: #27ae60; font-weight: bold;">+{total_in}</div>
                        <div style="font-size: 10px; color: #7f8c8d;">Stock In</div>
                    </div>
                    <div>
                        <div style="font-size: 12px; color: #e74c3c; font-weight: bold;">-{total_out}</div>
                        <div style="font-size: 10px; color: #7f8c8d;">Stock Out</div>
                    </div>
                </div>
                <div style="font-size: 10px; color: #95a5a6;">
                    📊 {obj.movements.count()} movements
                </div>
            </div>
        '''
        
        # Last movement info
        last_movement = obj.movements.order_by('-created_at').first()
        if last_movement:
            last_move_html = f'''
                <div style="font-size: 9px; color: #bdc3c7; margin-top: 2px;">
                    Last: {last_movement.get_movement_type_display()}
                </div>
            '''
        else:
            last_move_html = '<div style="font-size: 9px; color: #bdc3c7;">No movements</div>'
        
        return format_html(movement_html + last_move_html)
    movement_summary.short_description = 'Movements'
    
    def location_info(self, obj):
        """Display location information"""
        location_html = f'''
            <div style="text-align: center;">
                <div style="font-size: 13px; font-weight: 500; color: #2c3e50; margin-bottom: 2px;">
                    {obj.location or 'No Location'}
                </div>
        '''
        
        # Restock info
        if obj.last_restocked:
            days_ago = (timezone.now().date() - obj.last_restocked.date()).days
            restock_html = f'''
                <div style="font-size: 11px; color: #7f8c8d;">
                    🔄 {days_ago} days ago
                </div>
            '''
        else:
            restock_html = '<div style="font-size: 11px; color: #95a5a6;">Never restocked</div>'
        
        # Threshold info
        threshold_html = f'''
            <div style="font-size: 10px; color: #f39c12; margin-top: 2px;">
                Low stock alert: {obj.low_stock_threshold}
            </div>
        '''
        
        return format_html(location_html + restock_html + threshold_html)
    location_info.short_description = 'Location'
    
    def status_badges(self, obj):
        """Display status badges"""
        badges = []
        
        if obj.is_stock_out:
            badges.append('<span style="background-color: #e74c3c; color: white; padding: 4px 8px; border-radius: 12px; font-size: 10px; margin: 1px;">OUT OF STOCK</span>')
        elif obj.is_low_stock:
            badges.append('<span style="background-color: #f39c12; color: white; padding: 4px 8px; border-radius: 12px; font-size: 10px; margin: 1px;">LOW STOCK</span>')
        else:
            badges.append('<span style="background-color: #27ae60; color: white; padding: 4px 8px; border-radius: 12px; font-size: 10px; margin: 1px;">IN STOCK</span>')
        
        if obj.needs_restock:
            badges.append('<span style="background-color: #e67e22; color: white; padding: 4px 8px; border-radius: 12px; font-size: 10px; margin: 1px;">NEEDS RESTOCK</span>')
        
        if obj.reserved_quantity > 0:
            badges.append('<span style="background-color: #3498db; color: white; padding: 4px 8px; border-radius: 12px; font-size: 10px; margin: 1px;">RESERVED</span>')
        
        return format_html(' '.join(badges))
    status_badges.short_description = 'Status'
    
    def quick_actions(self, obj):
        """Display quick action buttons based on stock status and user permissions"""
        if obj.is_stock_out:
            if not self.user_is_superuser():
                # Non-superusers can only view out of stock items
                return format_html(
                    '''
                    <div class="quick-actions" style="display: flex; flex-direction: column; gap: 4px;">
                        <a href="{edit_url}" class="button" style="padding: 4px 8px; background: #3498db; color: white; 
                           text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center; display: block;">
                            ✏️ Edit
                        </a>
                        
                        <div style="padding: 4px 8px; background: #95a5a6; color: white; 
                             border-radius: 4px; font-size: 9px; text-align: center; cursor: not-allowed; opacity: 0.6;">
                            📥 Add Stock
                        </div>
                        
                        <div style="padding: 4px 8px; background: #95a5a6; color: white; 
                             border-radius: 4px; font-size: 9px; text-align: center; cursor: not-allowed; opacity: 0.6;">
                            🔧 Adjust
                        </div>
                        
                        <a href="{movements_url}" class="button" style="padding: 4px 8px; background: #9b59b6; color: white; 
                           text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center; display: block;">
                            📊 Movements
                        </a>
                        
                        <div style="font-size: 8px; color: #e74c3c; text-align: center; font-weight: bold; margin-top: 2px;">
                            SUPERUSER ONLY
                        </div>
                    </div>
                    ''',
                    edit_url=f'{obj.id}/change/',
                    movements_url=f'/admin/inventory/stockmovement/?inventory__id__exact={obj.id}'
                )
            else:
                # Superusers can restock out of stock items
                return format_html(
                    '''
                    <div class="quick-actions" style="display: flex; flex-direction: column; gap: 4px;">
                        <a href="{edit_url}" class="button" style="padding: 4px 8px; background: #3498db; color: white; 
                           text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center; display: block;">
                            ✏️ Edit
                        </a>
                        
                        <a href="{add_stock_url}" class="button" style="padding: 4px 8px; background: #27ae60; color: white; 
                           text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center; display: block;">
                            📥 Add Stock
                        </a>
                        
                        <a href="{adjust_stock_url}" class="button" style="padding: 4px 8px; background: #f39c12; color: white; 
                           text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center; display: block;">
                            🔧 Adjust
                        </a>
                        
                        <a href="{movements_url}" class="button" style="padding: 4px 8px; background: #9b59b6; color: white; 
                           text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center; display: block;">
                            📊 Movements
                        </a>
                        
                        <button type="button" onclick="quickRestock({inventory_id})" 
                                style="padding: 4px 8px; background: #e67e22; color: white; border: none; 
                                border-radius: 4px; font-size: 11px; cursor: pointer; margin-top: 2px;">
                            🚀 Quick Restock
                        </button>
                        
                        <div style="font-size: 8px; color: #f39c12; text-align: center; font-weight: bold; margin-top: 2px;">
                            SUPERUSER MODE
                        </div>
                    </div>
                    ''',
                    edit_url=f'{obj.id}/change/',
                    add_stock_url=f'/admin/inventory/inventory/{obj.id}/add-stock/',
                    adjust_stock_url=f'/admin/inventory/inventory/{obj.id}/adjust-stock/',
                    movements_url=f'/admin/inventory/stockmovement/?inventory__id__exact={obj.id}',
                    inventory_id=obj.id
                )
        else:
            # In-stock items - all users can edit
            return format_html(
                '''
                <div class="quick-actions" style="display: flex; flex-direction: column; gap: 4px;">
                    <a href="{edit_url}" class="button" style="padding: 4px 8px; background: #3498db; color: white; 
                       text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center; display: block;">
                        ✏️ Edit
                    </a>
                    
                    <a href="{add_stock_url}" class="button" style="padding: 4px 8px; background: #27ae60; color: white; 
                       text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center; display: block;">
                        📥 Add Stock
                    </a>
                    
                    <a href="{adjust_stock_url}" class="button" style="padding: 4px 8px; background: #f39c12; color: white; 
                       text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center; display: block;">
                        🔧 Adjust
                    </a>
                    
                    <a href="{movements_url}" class="button" style="padding: 4px 8px; background: #9b59b6; color: white; 
                       text-decoration: none; border-radius: 4px; font-size: 11px; text-align: center; display: block;">
                        📊 Movements
                    </a>
                    
                    <button type="button" onclick="quickRestock({inventory_id})" 
                            style="padding: 4px 8px; background: #e67e22; color: white; border: none; 
                            border-radius: 4px; font-size: 11px; cursor: pointer; margin-top: 2px;">
                        🚀 Quick Restock +10
                    </button>
                </div>
                
                <script>
                function quickRestock(inventoryId) {{
                    if (confirm('Quick restock: Add 10 units to this inventory?')) {{
                        fetch(`/admin/inventory/inventory/${{inventoryId}}/quick-restock/`, {{
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
                }}
                </script>
                ''',
                edit_url=f'{obj.id}/change/',
                add_stock_url=f'/admin/inventory/inventory/{obj.id}/add-stock/',
                adjust_stock_url=f'/admin/inventory/inventory/{obj.id}/adjust-stock/',
                movements_url=f'/admin/inventory/stockmovement/?inventory__id__exact={obj.id}',
                inventory_id=obj.id
            )
    quick_actions.short_description = 'Actions'
    
    def user_is_superuser(self):
        """Check if current user is superuser"""
        return hasattr(self, 'request') and self.request.user.is_superuser
    
    def changelist_view(self, request, extra_context=None):
        """Store request in instance for use in other methods"""
        self.request = request
        return super().changelist_view(request, extra_context=extra_context)
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Store request in instance for use in other methods"""
        self.request = request
        return super().changeform_view(request, object_id, form_url, extra_context=extra_context)
    
    # Custom URL handlers for button actions
    def add_stock_view(self, request, inventory_id):
        """Handle Add Stock button click"""
        inventory = self.get_object(request, inventory_id)
        
        if request.method == 'POST':
            quantity = int(request.POST.get('quantity', 0))
            if quantity > 0:
                inventory.add_stock(quantity)
                StockMovement.objects.create(
                    inventory=inventory,
                    movement_type='in',
                    quantity=quantity,
                    previous_quantity=inventory.quantity - quantity,
                    new_quantity=inventory.quantity,
                    reference='Manual Stock Add',
                    note=f'Added {quantity} units via Add Stock button',
                    created_by=request.user
                )
                messages.success(request, f'✅ Added {quantity} units to {inventory.product.products_name}')
                return redirect(reverse('admin:inventory_inventory_changelist'))
        
        return render(request, 'inventory/add_stock.html', {
            'inventory': inventory,
            'title': f'Add Stock - {inventory.product.products_name}'
        })
    
    def adjust_stock_view(self, request, inventory_id):
        """Handle Adjust Stock button click"""
        inventory = self.get_object(request, inventory_id)
        
        if request.method == 'POST':
            new_quantity = int(request.POST.get('quantity', inventory.quantity))
            adjustment_note = request.POST.get('note', '')
            
            if new_quantity >= 0:
                old_quantity = inventory.quantity
                inventory.quantity = new_quantity
                inventory.save()
                
                quantity_change = new_quantity - old_quantity
                StockMovement.objects.create(
                    inventory=inventory,
                    movement_type='adjustment',
                    quantity=quantity_change,
                    previous_quantity=old_quantity,
                    new_quantity=new_quantity,
                    reference='Manual Adjustment',
                    note=f'Stock adjusted from {old_quantity} to {new_quantity}. {adjustment_note}',
                    created_by=request.user
                )
                messages.success(request, f'✅ Stock adjusted to {new_quantity} units for {inventory.product.products_name}')
                return redirect(reverse('admin:inventory_inventory_changelist'))
        
        return render(request, 'inventory/adjust_stock.html', {
            'inventory': inventory,
            'title': f'Adjust Stock - {inventory.product.products_name}'
        })
    
    def quick_restock(self, request, inventory_id):
        """Handle Quick Restock button click (AJAX)"""
        if request.method == 'POST':
            try:
                inventory = Inventory.objects.get(id=inventory_id)
                restock_quantity = 10  # Default quick restock quantity

                # ✅ DO NOT call inventory.add_stock() here
                stock_movement = StockMovement.objects.create(
                    inventory=inventory,
                    movement_type='in',
                    quantity=restock_quantity,
                    reference='Quick Restock',
                    note=f'Quick restock: Added {restock_quantity} units via button',
                    created_by=request.user
                )

                return JsonResponse({
                    'success': True,
                    'message': f'Quick restock: Added {restock_quantity} units',
                    'new_quantity': stock_movement.new_quantity
                })
            except Inventory.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Inventory not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

    def bulk_add_stock_view(self, request):
        """Handle bulk add stock for multiple items"""
        if request.method == 'POST':
            inventory_ids = request.POST.getlist('inventory_ids')
            quantity = int(request.POST.get('quantity', 0))
            
            if inventory_ids and quantity > 0:
                inventories = Inventory.objects.filter(id__in=inventory_ids)
                for inventory in inventories:
                    inventory.add_stock(quantity)
                    StockMovement.objects.create(
                        inventory=inventory,
                        movement_type='in',
                        quantity=quantity,
                        previous_quantity=inventory.quantity - quantity,
                        new_quantity=inventory.quantity,
                        reference='Bulk Stock Add',
                        note=f'Added {quantity} units via bulk action',
                        created_by=request.user
                    )
                
                messages.success(request, f'✅ Added {quantity} units to {inventories.count()} items')
                return redirect(reverse('admin:inventory_inventory_changelist'))
        
        # Get selected inventory items from GET parameters
        inventory_ids = request.GET.get('ids', '').split(',')
        inventories = Inventory.objects.filter(id__in=[id for id in inventory_ids if id])
        
        return render(request, 'admin/inventory/bulk_add_stock.html', {
            'inventories': inventories,
            'title': 'Bulk Add Stock'
        })
    
    # Custom methods for calculations
    def total_stock_in(self, obj):
        return obj.movements.filter(
            movement_type__in=['in', 'return', 'adjustment'],
            quantity__gt=0
        ).aggregate(total=Sum('quantity'))['total'] or 0
    total_stock_in.short_description = "Total Stock In"

    def total_stock_out(self, obj):
        result = obj.movements.filter(
            movement_type__in=['out', 'reserved']
        ).aggregate(total=Sum('quantity'))['total'] or 0
        return abs(result)  # Return positive value for display
    total_stock_out.short_description = "Total Stock Out"

# ... (Keep the StockMovementAdmin and StockAlertAdmin classes from previous implementation)



@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'movement_card',
        'inventory_info',
        'quantity_change',
        'reference_info',
        'timestamp_info'
    )
    
    list_display_links = None
    list_per_page = 20
    
    list_filter = ('movement_type', 'created_at')
    search_fields = ('inventory__product__products_name', 'reference', 'note')
    readonly_fields = ('previous_quantity', 'new_quantity', 'created_at', 'created_by')
    
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('inventory__product', 'created_by')
    
    def movement_card(self, obj):
        """Display movement as a card"""
        # Movement type color
        movement_colors = {
            'in': '#27ae60',
            'out': '#e74c3c',
            'adjustment': '#f39c12',
            'return': '#3498db',
            'reserved': '#9b59b6',
            'released': '#34495e'
        }
        movement_color = movement_colors.get(obj.movement_type, '#95a5a6')
        
        # Quantity display with sign
        quantity_display = f"+{obj.quantity}" if obj.quantity > 0 else str(obj.quantity)
        
        return format_html(
            '''
            <div style="display: flex; align-items: center; gap: 12px; padding: 8px 0;">
                <div style="flex-shrink: 0;">
                    <div style="width: 50px; height: 50px; background: {color}; color: white; 
                         border-radius: 8px; display: flex; align-items: center; justify-content: center; 
                         font-weight: bold; font-size: 14px;">
                        {quantity}
                    </div>
                </div>
                <div style="flex-grow: 1; min-width: 0;">
                    <div style="font-size: 13px; font-weight: 500; color: #2c3e50; margin-bottom: 2px;">
                        {movement_type}
                    </div>
                    <div style="font-size: 11px; color: #7f8c8d;">
                        {product_name}
                    </div>
                    <div style="font-size: 10px; color: #95a5a6;">
                        {reference}
                    </div>
                </div>
            </div>
            ''',
            color=movement_color,
            quantity=quantity_display,
            movement_type=obj.get_movement_type_display(),
            product_name=obj.inventory.product.products_name,
            reference=obj.reference or 'No reference'
        )
    movement_card.short_description = 'Movement'
    
    def inventory_info(self, obj):
        """Display inventory information"""
        return format_html(
            '''
            <div style="text-align: center;">
                <div style="font-size: 12px; font-weight: 500; color: #2c3e50; margin-bottom: 2px;">
                    {location}
                </div>
                <div style="font-size: 11px; color: #7f8c8d;">
                    Stock: {current_qty}
                </div>
            </div>
            ''',
            location=obj.inventory.location or 'No Location',
            current_qty=obj.inventory.quantity
        )
    inventory_info.short_description = 'Inventory'
    
    def quantity_change(self, obj):
        """Display quantity change"""
        return format_html(
            '''
            <div style="text-align: center;">
                <div style="font-size: 14px; font-weight: bold; color: {color}; margin-bottom: 2px;">
                    {quantity}
                </div>
                <div style="font-size: 11px; color: #7f8c8d;">
                    {from_qty} → {to_qty}
                </div>
            </div>
            ''',
            color='#27ae60' if obj.quantity > 0 else '#e74c3c',
            quantity=f"+{obj.quantity}" if obj.quantity > 0 else obj.quantity,
            from_qty=obj.previous_quantity,
            to_qty=obj.new_quantity
        )
    quantity_change.short_description = 'Quantity Change'
    
    def reference_info(self, obj):
        """Display reference information"""
        return format_html(
            '''
            <div style="text-align: center;">
                <div style="font-size: 11px; color: #2c3e50; margin-bottom: 2px;">
                    {user}
                </div>
                <div style="font-size: 10px; color: #7f8c8d; line-height: 1.2;">
                    {note}
                </div>
            </div>
            ''',
            user=obj.created_by.username if obj.created_by else 'System',
            note=obj.note or 'No notes'
        )
    reference_info.short_description = 'Reference'
    
    def timestamp_info(self, obj):
        """Display timestamp information"""
        return format_html(
            '''
            <div style="text-align: center;">
                <div style="font-size: 11px; color: #2c3e50; margin-bottom: 2px;">
                    {date}
                </div>
                <div style="font-size: 10px; color: #7f8c8d;">
                    {time}
                </div>
            </div>
            ''',
            date=obj.created_at.strftime('%b %d, %Y'),
            time=obj.created_at.strftime('%H:%M')
        )
    timestamp_info.short_description = 'Timestamp'

@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = (
        'alert_card',
        'inventory_info',
        'alert_type_badge',
        'status_badge',
        'timestamp_info',
        'quick_actions'
    )
    
    list_display_links = None
    list_per_page = 20
    
    list_filter = ('alert_type', 'status', 'created_at')
    search_fields = ('inventory__product__products_name', 'message')
    readonly_fields = ('created_at', 'resolved_at')
    
    actions = ['resolve_alerts', 'dismiss_alerts']
    
    def alert_card(self, obj):
        """Display alert as a card"""
        # Alert type color
        alert_colors = {
            'low_stock': '#f39c12',
            'out_of_stock': '#e74c3c',
            'over_stock': '#3498db'
        }
        alert_color = alert_colors.get(obj.alert_type, '#95a5a6')
        
        return format_html(
            '''
            <div style="display: flex; align-items: center; gap: 12px; padding: 8px 0;">
                <div style="flex-shrink: 0;">
                    <div style="width: 50px; height: 50px; background: {color}; color: white; 
                         border-radius: 8px; display: flex; align-items: center; justify-content: center; 
                         font-size: 20px;">
                        {icon}
                    </div>
                </div>
                <div style="flex-grow: 1; min-width: 0;">
                    <div style="font-size: 13px; font-weight: 500; color: #2c3e50; margin-bottom: 2px;">
                        {product_name}
                    </div>
                    <div style="font-size: 11px; color: #7f8c8d; line-height: 1.2;">
                        {message}
                    </div>
                </div>
            </div>
            ''',
            color=alert_color,
            icon='⚠️' if obj.alert_type == 'low_stock' else '❌' if obj.alert_type == 'out_of_stock' else '📦',
            product_name=obj.inventory.product.products_name,
            message=obj.message
        )
    alert_card.short_description = 'Alert'
    
    def inventory_info(self, obj):
        """Display inventory information"""
        return format_html(
            '''
            <div style="text-align: center;">
                <div style="font-size: 12px; font-weight: 500; color: #2c3e50; margin-bottom: 2px;">
                    {location}
                </div>
                <div style="font-size: 11px; color: #7f8c8d;">
                    Stock: {quantity}
                </div>
            </div>
            ''',
            location=obj.inventory.location or 'No Location',
            quantity=obj.inventory.quantity
        )
    inventory_info.short_description = 'Inventory'
    
    def alert_type_badge(self, obj):
        """Display alert type as badge"""
        colors = {
            'low_stock': '#f39c12',
            'out_of_stock': '#e74c3c',
            'over_stock': '#3498db'
        }
        color = colors.get(obj.alert_type, '#95a5a6')
        
        return format_html(
            '''
            <span style="background-color: {color}; color: white; padding: 4px 8px; 
                  border-radius: 12px; font-size: 10px; font-weight: bold;">
                {alert_type}
            </span>
            ''',
            color=color,
            alert_type=obj.get_alert_type_display()
        )
    alert_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        """Display status as badge"""
        color = '#27ae60' if obj.status == 'resolved' else '#f39c12' if obj.status == 'active' else '#95a5a6'
        
        return format_html(
            '''
            <span style="background-color: {color}; color: white; padding: 4px 8px; 
                  border-radius: 12px; font-size: 10px; font-weight: bold;">
                {status}
            </span>
            ''',
            color=color,
            status=obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def timestamp_info(self, obj):
        """Display timestamp information"""
        if obj.resolved_at:
            timestamp_html = f'''
                <div style="text-align: center;">
                    <div style="font-size: 11px; color: #27ae60; margin-bottom: 2px;">
                        Resolved
                    </div>
                    <div style="font-size: 10px; color: #7f8c8d;">
                        {obj.resolved_at.strftime('%b %d, %Y')}
                    </div>
                </div>
            '''
        else:
            timestamp_html = f'''
                <div style="text-align: center;">
                    <div style="font-size: 11px; color: #f39c12; margin-bottom: 2px;">
                        Active
                    </div>
                    <div style="font-size: 10px; color: #7f8c8d;">
                        {obj.created_at.strftime('%b %d, %Y')}
                    </div>
                </div>
            '''
        
        return format_html(timestamp_html)
    timestamp_info.short_description = 'Timeline'
    
    def quick_actions(self, obj):
        """Display quick actions"""
        if obj.status == 'active':
            return format_html(
                '''
                <div style="display: flex; flex-direction: column; gap: 3px;">
                    <button type="button" onclick="handleAlertAction({alert_id}, 'resolve')" 
                            style="padding: 3px 6px; background: #27ae60; color: white; border: none; 
                            border-radius: 3px; font-size: 10px; cursor: pointer;">
                        Resolve
                    </button>
                    <button type="button" onclick="handleAlertAction({alert_id}, 'dismiss')" 
                            style="padding: 3px 6px; background: #95a5a6; color: white; border: none; 
                            border-radius: 3px; font-size: 10px; cursor: pointer;">
                        Dismiss
                    </button>
                    <a href="{inventory_url}" style="padding: 3px 6px; background: #3498db; color: white; 
                       text-decoration: none; border-radius: 3px; font-size: 10px; text-align: center;">
                        View Inventory
                    </a>
                </div>
                
                <script>
                function handleAlertAction(alertId, action) {{
                    fetch(`/admin/inventory/stockalert/${{alertId}}/${{action}}/`, {{
                        method: 'POST',
                        headers: {{
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
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
                alert_id=obj.id,
                inventory_url=f'/admin/inventory/inventory/{obj.inventory.id}/change/'
            )
        else:
            return format_html(
                '''
                <div style="font-size: 10px; color: #95a5a6; text-align: center;">
                    {status}
                </div>
                ''',
                status=obj.get_status_display().upper()
            )
    quick_actions.short_description = 'Actions'
    
    # Custom Actions
    def resolve_alerts(self, request, queryset):
        """Resolve selected alerts"""
        resolved = queryset.filter(status='active').update(
            status='resolved',
            resolved_at=timezone.now()
        )
        self.message_user(
            request,
            f'Resolved {resolved} alerts.',
            messages.SUCCESS
        )
    resolve_alerts.short_description = "Resolve selected alerts"
    
    def dismiss_alerts(self, request, queryset):
        """Dismiss selected alerts"""
        dismissed = queryset.filter(status='active').update(status='dismissed')
        self.message_user(
            request,
            f'Dismissed {dismissed} alerts.',
            messages.WARNING
        )
    dismiss_alerts.short_description = "Dismiss selected alerts"