from django.contrib import admin
from .models import Promotion, PromotionUsage, PromotionCode

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'promo_type', 'discount_value', 'is_active', 'start_date', 'end_date', 'created_by']
    list_filter = ['promo_type', 'is_active', 'start_date', 'end_date']
    search_fields = ['name', 'code', 'description']
    date_hierarchy = 'start_date'
    filter_horizontal = ['products']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'promo_type', 'discount_value')
        }),
        ('Products', {
            'fields': ('products',)
        }),
        ('Usage Limits', {
            'fields': ('usage_limit', 'user_limit')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.user_type == 'admin' and not request.user.is_superuser:
            return qs.filter(created_by=request.user)
        return qs

@admin.register(PromotionUsage)
class PromotionUsageAdmin(admin.ModelAdmin):
    list_display = ['promotion', 'user', 'order_id', 'used_at']
    list_filter = ['promotion', 'used_at']
    search_fields = ['promotion__name', 'user__username', 'order_id']
    date_hierarchy = 'used_at'
    readonly_fields = ['used_at']

@admin.register(PromotionCode)
class PromotionCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'promotion', 'is_active', 'created_at']
    list_filter = ['is_active', 'promotion']
    search_fields = ['code', 'promotion__name']
    readonly_fields = ['created_at']
