# inventory/admin.py
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db import models
from .models import Inventory

# Custom filter for stock status
class StockStatusFilter(SimpleListFilter):
    title = 'Stock Status'
    parameter_name = 'stock_status'

    def lookups(self, request, model_admin):
        return (
            ('out', 'Stock Out'),
            ('upcoming', 'Upcoming Stock Out'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'out':
            return queryset.filter(quantity=0)
        if self.value() == 'upcoming':
            return queryset.filter(quantity__lte=models.F('low_stock_threshold'), quantity__gt=0)

# Register InventoryAdmin with stock status and filter
@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'low_stock_threshold', 'stock_status')
    list_filter = ('product__category', StockStatusFilter)
    search_fields = ('product__name',)

    def stock_status(self, obj):
        if obj.is_stock_out:
            return "Stock Out"
        elif obj.is_upcoming_stock_out:
            return "Upcoming Stock Out"
        else:
            return "In Stock"
    stock_status.short_description = "Stock Status"
