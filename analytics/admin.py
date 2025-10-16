from django.contrib import admin
from .models import Customer, AnalyticsSnapshot

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'total_orders', 'total_spent', 'created_at')
    search_fields = ('name', 'email', 'phone')