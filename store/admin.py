from django.contrib import admin
from .models import Category, Brand

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'brand')
    search_fields = ('name',)
    list_filter = ('parent',)

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'logo')
    search_fields = ('name',)
