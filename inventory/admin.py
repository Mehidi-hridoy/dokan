# inventory/admin.py
from django.contrib import admin, messages
from django.db import models
from django.utils.html import format_html
from django import forms
from .models import Inventory, StockMovement, StockAlert


# ----------------------------------------------------------------------
# Inline for StockMovement
# ----------------------------------------------------------------------
class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 1
    fields = ('movement_type', 'quantity', 'reference', 'note', 'created_by', 'created_at')
    readonly_fields = ('previous_quantity', 'new_quantity', 'created_at')

# ----------------------------------------------------------------------
# Inline for StockAlert
# ----------------------------------------------------------------------
class StockAlertInline(admin.TabularInline):
    model = StockAlert
    extra = 0
    fields = ('alert_type', 'message', 'status', 'resolved_at')
    readonly_fields = ('created_at', 'resolved_at')

# ----------------------------------------------------------------------
# Admin for Inventory
# ----------------------------------------------------------------------
@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'reserved_quantity', 'available_quantity', 'stock_status', 'location', 'last_restocked')
    list_filter = ('location', 'last_restocked', 'created_at', 'low_stock_threshold')
    search_fields = ('product__products_name', 'batch_number', 'location')
    ordering = ('-last_updated',)
    inlines = [StockMovementInline, StockAlertInline]
    readonly_fields = ('available_quantity', 'created_at', 'last_updated')

    fieldsets = (
        (None, {
            'fields': ('product', 'quantity', 'reserved_quantity', 'location', 'batch_number')
        }),
        ('Thresholds', {
            'fields': ('low_stock_threshold', 'reorder_quantity')
        }),
        ('Tracking (read-only)', {
            'fields': ('available_quantity', 'last_restocked', 'last_updated', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def stock_status(self, obj):
        """Colored status badge"""
        if obj.is_stock_out:
            color = 'red'
            text = 'Out'
        elif obj.is_low_stock:
            color = 'orange'
            text = 'Low'
        else:
            color = 'green'
            text = 'OK'
        return format_html('<span style="color: white; background: {}; padding: 2px 6px; border-radius: 4px;">{}</span>', color, text)
    stock_status.short_description = 'Status'

    actions = ['restock_selected', 'reserve_selected']

    def restock_selected(self, request, queryset):
        for obj in queryset:
            obj.add_stock(obj.reorder_quantity, created_by=request.user)
        self.message_user(request, "Selected items restocked.", messages.SUCCESS)
    restock_selected.short_description = "Restock selected (add reorder qty)"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')

# ----------------------------------------------------------------------
# Admin for StockMovement
# ----------------------------------------------------------------------
@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('inventory', 'movement_type', 'quantity', 'reference', 'created_by', 'created_at')
    list_filter = ('movement_type', 'created_at', 'created_by')
    search_fields = ('inventory__product__products_name', 'reference', 'note')
    readonly_fields = ('previous_quantity', 'new_quantity', 'created_at')
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('inventory', 'movement_type', 'quantity', 'reference', 'note', 'created_by')
        }),
        ('Audit', {
            'fields': ('previous_quantity', 'new_quantity', 'created_at'),
            'classes': ('collapse',)
        }),
    )

# ----------------------------------------------------------------------
# Admin for StockAlert
# ----------------------------------------------------------------------
@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('inventory', 'alert_type', 'status', 'created_at', 'resolved_at')
    list_filter = ('alert_type', 'status', 'created_at')
    search_fields = ('inventory__product__products_name', 'message')
    readonly_fields = ('created_at', 'resolved_at')
    actions = ['resolve_alerts', 'dismiss_alerts']

    def resolve_alerts(self, request, queryset):
        updated = queryset.update(status='resolved', resolved_at=timezone.now(), resolved_by=request.user)
        self.message_user(request, f"{updated} alert(s) resolved.", messages.SUCCESS)
    resolve_alerts.short_description = "Resolve selected alerts"

    def dismiss_alerts(self, request, queryset):
        updated = queryset.update(status='dismissed')
        self.message_user(request, f"{updated} alert(s) dismissed.", messages.SUCCESS)
    dismiss_alerts.short_description = "Dismiss selected alerts"