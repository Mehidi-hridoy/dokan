from django.contrib import admin
from .models import Customer
from .models import Expense, ExpenseCategory,FinancialRecord,DamageReport
from django.utils.html import format_html


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'customer_type', 'total_orders', 'total_spent', 'is_fraudulent']
    list_filter = ['customer_type', 'is_fraudulent', 'created_at']
    search_fields = ['name', 'email', 'phone']

@admin.register(FinancialRecord)
class FinancialRecordAdmin(admin.ModelAdmin):
    list_display = ['record_type', 'amount', 'description', 'date', 'created_by']
    list_filter = ['record_type', 'date']
    search_fields = ['description', 'reference']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color_display', 'description']
    
    def color_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border-radius: 3px;"></div>',
            obj.color
        )
    color_display.short_description = 'Color'

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['category', 'amount', 'description', 'date', 'created_by']
    list_filter = ['category', 'date']
    search_fields = ['description']

@admin.register(DamageReport)
class DamageReportAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity', 'damage_type', 'cost_amount', 'resolved', 'date_reported']
    list_filter = ['damage_type', 'resolved', 'date_reported']
    search_fields = ['product__products_name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def mark_as_resolved(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(resolved=True, resolved_at=timezone.now(), resolved_by=request.user)
        self.message_user(request, f'{updated} damage reports marked as resolved.')
    mark_as_resolved.short_description = "Mark selected damage reports as resolved"