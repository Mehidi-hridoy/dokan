from django.contrib import admin
from .models import Brand, Category

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'logo')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'brand')
    search_fields = ('name', 'slug')
    list_filter = ('brand',)
    prepopulated_fields = {'slug': ('name',)}
