from django.contrib import admin
from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from django.utils.html import format_html
from .models import Product, ProductImage

class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'short_description': CKEditor5Widget(config_name='extends'),
            'description': CKEditor5Widget(config_name='extends'),
        }

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ('name', 'product_code', 'image_tag', 'price', 'user', 'is_active', 'is_featured', 'stock_option', 'quantity', 'created_at')
    list_filter = ('category', 'brand', 'is_active', 'is_featured', 'stock_option')
    search_fields = ('name', 'product_code', 'sku', 'tags')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active', 'is_featured')
    filter_horizontal = ('gallery_images',)
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'product_code', 'category', 'sub_category', 'brand', 'user')
        }),
        ('Pricing & Stock', {
            'fields': ('price', 'previous_price', 'stock_option', 'quantity', 'inventory')
        }),
        ('Details', {
            'fields': ('short_description', 'description', 'color', 'size', 'weight', )
        }),
        ('Images', {
            'fields': ('products_image', 'gallery_images')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'tags')
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            # Regular users see only themselves as the user and cannot edit
            form.base_fields['user'].queryset = form.base_fields['user'].queryset.filter(pk=request.user.pk)
            form.base_fields['user'].initial = request.user
            form.base_fields['user'].disabled = True
        return form

    def save_model(self, request, obj, form, change):
        # Automatically assign logged-in user if creating
        if not obj.pk and not request.user.is_superuser:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    def image_tag(self, obj):
        if obj.products_image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;">', obj.products_image.url)
        return "-"
    image_tag.short_description = 'Image'



@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('alt_text', 'image')
    search_fields = ('alt_text',)
