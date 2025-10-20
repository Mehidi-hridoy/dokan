from django.contrib import admin
from .models import Category, Brand

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'brand')
    search_fields = ('name', 'slug')
    list_filter = ('parent', 'brand')
    prepopulated_fields = {'slug': ('name',)}  # Auto-fill slug from name

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'logo')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}  # Auto-fill slug from name
