from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse

User = get_user_model()

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class Category(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='children')
    is_active = models.BooleanField(default=True)
    meta_title = models.CharField(max_length=200, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    ordering = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['ordering', 'name']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('category_products', kwargs={'slug': self.slug})
    
    @property
    def product_count(self):
        return self.products.count()

class Brand(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = _('Brand')
        verbose_name_plural = _('Brands')
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('brand_products', kwargs={'slug': self.slug})
    
    @property
    def product_count(self):
        return self.products.count()

class Attribute(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=20, choices=[
        ('text', 'Text'),
        ('number', 'Number'),
        ('color', 'Color'),
        ('select', 'Select'),
    ], default='select')
    
    class Meta:
        verbose_name = _('Attribute')
        verbose_name_plural = _('Attributes')
        ordering = ['name']
    
    def __str__(self):
        return self.name

class AttributeValue(TimeStampedModel):
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=100)
    color_code = models.CharField(max_length=7, blank=True, null=True, help_text="Hex color code for color type attributes")
    ordering = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = _('Attribute Value')
        verbose_name_plural = _('Attribute Values')
        unique_together = ['attribute', 'value']
        ordering = ['attribute', 'ordering', 'value']
    
    def __str__(self):
        return f"{self.attribute.name}: {self.value}"

class Product(TimeStampedModel):
    STATUS_CHOICES = (
        ('draft', _('Draft')),
        ('published', _('Published')),
        ('archived', _('Archived')),
    )
    
    TYPE_CHOICES = (
        ('simple', _('Simple')),
        ('variable', _('Variable')),
    )
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField()
    short_description = models.TextField(max_length=500, blank=True, null=True)
    sku = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='simple')
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    
    # Relations
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, blank=True, null=True, related_name='products')
    
    # Status & Features
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    featured = models.BooleanField(default=False)
    track_inventory = models.BooleanField(default=True)
    
    # Physical Properties
    weight = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    length = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    width = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    height = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    
    # Additional Fields
    tags = models.CharField(max_length=500, blank=True, null=True)
    ordering = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = _('Product')
        verbose_name_plural = _('Products')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'featured']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['sku']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('product_detail', kwargs={'slug': self.slug})
    
    @property
    def discount_percentage(self):
        if self.compare_price and self.compare_price > self.price:
            return int(((self.compare_price - self.price) / self.compare_price) * 100)
        return 0
    
    @property
    def in_stock(self):
        if hasattr(self, 'inventory'):
            return self.inventory.quantity > 0
        return False
    
    @property
    def stock_quantity(self):
        if hasattr(self, 'inventory'):
            return self.inventory.quantity
        return 0
    
    @property
    def primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()

class ProductImage(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    ordering = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = _('Product Image')
        verbose_name_plural = _('Product Images')
        ordering = ['is_primary', 'ordering']
    
    def __str__(self):
        return f"Image for {self.product.name}"
    
    def save(self, *args, **kwargs):
        # If this image is set as primary, unset primary for other images of the same product
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)

class ProductAttribute(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attributes_link')
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    values = models.ManyToManyField(AttributeValue, related_name='product_attributes')
    
    class Meta:
        verbose_name = _('Product Attribute')
        verbose_name_plural = _('Product Attributes')
        unique_together = ['product', 'attribute']
    
    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}"

class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    weight = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    attributes = models.ManyToManyField(AttributeValue, through='VariantAttribute')
    is_default = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = _('Product Variant')
        verbose_name_plural = _('Product Variants')
        ordering = ['-is_default', 'sku']
    
    def __str__(self):
        return f"{self.product.name} - {self.sku}"
    
    @property
    def discount_percentage(self):
        if self.compare_price and self.compare_price > self.price:
            return int(((self.compare_price - self.price) / self.compare_price) * 100)
        return 0

class VariantAttribute(TimeStampedModel):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='variant_attributes')
    attribute_value = models.ForeignKey(AttributeValue, on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = _('Variant Attribute')
        verbose_name_plural = _('Variant Attributes')
        unique_together = ['variant', 'attribute_value']
    
    def __str__(self):
        return f"{self.variant.sku} - {self.attribute_value}"
class Inventory(TimeStampedModel):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='inventory')
    quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    low_stock_threshold = models.IntegerField(default=10, validators=[MinValueValidator(0)])
    reorder_level = models.IntegerField(default=5, validators=[MinValueValidator(0)])
    reserved_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    class Meta:
        verbose_name = _('Inventory')
        verbose_name_plural = _('Inventories')
    
    def __str__(self):
        return f"Inventory for {self.product.name}"
    
    @property
    def available_quantity(self):
        return self.quantity - self.reserved_quantity
    
    @property
    def in_stock(self):
        return self.available_quantity > 0
    
    @property
    def is_low_stock(self):
        return self.available_quantity <= self.low_stock_threshold
    
    @property
    def needs_reorder(self):
        return self.available_quantity <= self.reorder_level

class VariantInventory(TimeStampedModel):
    variant = models.OneToOneField(ProductVariant, on_delete=models.CASCADE, related_name='inventory')
    quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    low_stock_threshold = models.IntegerField(default=10, validators=[MinValueValidator(0)])
    reorder_level = models.IntegerField(default=5, validators=[MinValueValidator(0)])
    reserved_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    class Meta:
        verbose_name = _('Variant Inventory')
        verbose_name_plural = _('Variant Inventories')
    
    def __str__(self):
        return f"Inventory for {self.variant.sku}"
    
    @property
    def available_quantity(self):
        return self.quantity - self.reserved_quantity
    
    @property
    def in_stock(self):
        return self.available_quantity > 0
    
    @property
    def is_low_stock(self):
        return self.available_quantity <= self.low_stock_threshold

class ProductReview(TimeStampedModel):
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=RATING_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=200)
    comment = models.TextField()
    is_approved = models.BooleanField(default=False)
    helpful_count = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = _('Product Review')
        verbose_name_plural = _('Product Reviews')
        unique_together = ['product', 'user']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Review for {self.product.name} by {self.user.email}"
    
    @property
    def rating_stars(self):
        return '★' * self.rating + '☆' * (5 - self.rating)

class Wishlist(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    
    class Meta:
        verbose_name = _('Wishlist')
        verbose_name_plural = _('Wishlist')
        unique_together = ['user', 'product']
    
    def __str__(self):
        return f"{self.user.email} - {self.product.name}"