from django.db import models
from django_ckeditor_5.fields import CKEditor5Field
from django.utils.text import slugify
from django.db.models import Max
import re
import uuid
from store.models import Category, Brand
from users.models import User
from inventory.models import Inventory

COLOR_CHOICES = [
    ('Red', 'Red'), ('Blue', 'Blue'), ('Pink', 'Pink'), ('Orange', 'Orange'),
    ('Yellow', 'Yellow'), ('Green', 'Green'), ('Brown', 'Brown')
]
WEIGHT_CHOICES = [
    ('500gm', '500 gm'), ('1kg', '1 kg'), ('2kg', '2 kg'), ('5kg', '5 kg')
]
SIZE_CHOICES = [
    ('S', 'Small'), ('M', 'Medium'), ('L', 'Large'), ('XL', 'XL'), ('XXL', 'XXL')
]

class ProductManager(models.Manager):
    def in_stock(self):
        """Return products that are in stock"""
        return self.filter(is_active=True, inventory__quantity__gt=0)
    
    def low_stock(self):
        """Return products with low stock"""
        return self.filter(
            is_active=True,
            inventory__quantity__lte=models.F('inventory__low_stock_threshold'),
            inventory__quantity__gt=0
        )
    
    def out_of_stock(self):
        """Return out of stock products"""
        return self.filter(
            is_active=True,
            inventory__quantity=0
        )

class Product(models.Model):
    # Basic Information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products',null=True, blank=True)
    products_name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    product_code = models.CharField(max_length=20, unique=True, blank=True)
    short_description = CKEditor5Field(blank=True, null=True, config_name='extends')
    description = CKEditor5Field(blank=True, null=True, config_name='extends')

    # Categorization
    category = models.ForeignKey(Category, on_delete=models.CASCADE, blank=True, null=True, related_name='products')
    sub_category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='sub_products', blank=True, null=True)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)

    # Pricing Information (Managed in Products app only)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Base price without any discounts")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Current selling price")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Cost price for profit calculation")
    
    # Stock Management (Read-only from Inventory)
    stock_managed_by_inventory = models.BooleanField(default=True, help_text="If checked, stock is managed by Inventory app")
    
    # Product Variants
    color = models.CharField(max_length=50, choices=COLOR_CHOICES, blank=True, null=True)
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, blank=True, null=True)
    weight = models.CharField(max_length=10, choices=WEIGHT_CHOICES, blank=True, null=True)

    # Images
    products_image = models.ImageField(upload_to='products/images/', blank=True, null=True)
    gallery_images = models.ManyToManyField('ProductImage', blank=True,related_name='product_gallery',)

    # SEO
    meta_title = models.CharField(max_length=255, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    tags = models.CharField(max_length=255, blank=True, null=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'is_published']),
            models.Index(fields=['base_price']),
            models.Index(fields=['category']),
            models.Index(fields=['brand']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.products_name)

        if not self.product_code:
            prefix = 'DK07'
            last_id = Product.objects.aggregate(last_id=Max('id'))['last_id'] or 0
            counter = last_id + 1
            uuid_segment = str(uuid.uuid4())[:4].upper()
            self.product_code = f"{prefix}{counter:05d}-{uuid_segment}"
            while Product.objects.filter(product_code=self.product_code).exists():
                counter += 1
                self.product_code = f"{prefix}{counter:05d}-{uuid_segment}"

        if self.description:
            text = re.sub(r'<[^>]+>', '', self.description)
            words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
            unique_words = list(dict.fromkeys(words))
            self.tags = ', '.join(unique_words[:10])

        # Set sale price if not provided
        if not self.sale_price:
            self.sale_price = self.base_price

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.products_name} ({self.product_code})"

    @property
    def current_price(self):
        """Get current price (sale price if available, otherwise base price)"""
        return self.sale_price or self.base_price

    @property
    def is_in_stock(self):
        """Check if product is in stock through inventory"""
        if hasattr(self, 'inventory'):
            return self.inventory.quantity > 0
        return False

    @property
    def available_quantity(self):
        """Get available quantity from inventory"""
        if hasattr(self, 'inventory'):
            return self.inventory.quantity
        return 0

    @property
    def is_low_stock(self):
        """Check if product is low in stock"""
        if hasattr(self, 'inventory'):
            return 0 < self.inventory.quantity <= self.inventory.low_stock_threshold
        return False

    @property
    def profit_margin(self):
        """Calculate profit margin if cost price is available"""
        if self.cost_price and self.current_price:
            return ((self.current_price - self.cost_price) / self.cost_price) * 100
        return None

    def get_price_for_order(self):
        """Get price to be used in orders (immutable once order is created)"""
        return self.current_price


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/gallery/')
    alt_text = models.CharField(max_length=255, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['is_primary', 'display_order', '-id']

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Ensure only one primary image per product
            ProductImage.objects.filter(product=self.product, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.alt_text or f"Image for {self.product.products_name}"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    is_approved = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['product', 'user']  # One review per user per product

    def __str__(self):
        return f"Review by {self.user.username} for {self.product.products_name} - {self.rating} stars"