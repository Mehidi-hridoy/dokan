# analytics/admin.py

from django.contrib import admin
from .models import Customer, FinancialRecord, ExpenseCategory, Expense, DamageReport

# --- Customer Admin ---
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'total_orders', 'total_spent', 'customer_type', 'is_fraudulent', 'is_guest', 'created_at')
    list_filter = ('customer_type', 'is_fraudulent', 'is_guest', 'created_at')
    search_fields = ('name', 'email', 'phone', 'user__username')
    readonly_fields = ('total_orders', 'total_spent', 'first_order_date', 'last_order_date', 'created_at', 'updated_at', 'ip_address')
    actions = ['mark_as_fraudulent', 'mark_as_not_fraudulent']
    
    fieldsets = (
        ('Customer Profile', {
            'fields': ('user', 'name', 'email', 'phone', 'avatar', 'ip_address')
        }),
        ('Analytics & Status', {
            'fields': ('customer_type', 'is_fraudulent', 'is_guest'),
        }),
        ('Order Statistics', {
            'fields': ('total_orders', 'total_spent', 'first_order_date', 'last_order_date'),
        }),
    )

    @admin.action(description='Mark selected customers as fraudulent')
    def mark_as_fraudulent(self, request, queryset):
        queryset.update(is_fraudulent=True, customer_type='fraud')
        self.message_user(request, f"{queryset.count()} customers marked as fraudulent.")

    @admin.action(description='Mark selected customers as NOT fraudulent')
    def mark_as_not_fraudulent(self, request, queryset):
        queryset.update(is_fraudulent=False)
        for customer in queryset:
            customer.update_customer_stats() # Recalculate type
        self.message_user(request, f"{queryset.count()} customers marked as not fraudulent.")


# --- Financial Admin ---
@admin.register(FinancialRecord)
class FinancialRecordAdmin(admin.ModelAdmin):
    list_display = ('record_type', 'amount', 'date', 'reference', 'created_by')
    list_filter = ('record_type', 'date')
    search_fields = ('description', 'reference')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'color')
    search_fields = ('name',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('category', 'amount', 'date', 'description', 'created_by')
    list_filter = ('category', 'date')
    search_fields = ('description',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DamageReport)
class DamageReportAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'damage_type', 'cost_amount', 'date_reported', 'resolved')
    list_filter = ('damage_type', 'resolved', 'date_reported')
    search_fields = ('product__products_name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['mark_resolved']

    @admin.action(description='Mark selected damage reports as resolved')
    def mark_resolved(self, request, queryset):
        queryset.filter(resolved=False).update(resolved=True, resolved_at=timezone.now())
        self.message_user(request, f"{queryset.filter(resolved=True).count()} reports marked as resolved.")