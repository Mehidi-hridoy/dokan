from django.db import models
from django_ckeditor_5.fields import CKEditor5Field
from django.utils.text import slugify
from django.db.models import Max
import re
import uuid
from store.models import Category, Brand
from users.models import User

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
UNIT_CHOICES = [('Small', 'Small'), ('Large', 'Large')]
STOCK_OPTION = [('Manual', 'Manual'), ('Inventory', 'Inventory')]

class Product(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    product_code = models.CharField(max_length=20, unique=True, blank=True)
    short_description = CKEditor5Field(blank=True, null=True, config_name='extends')
    description = CKEditor5Field(blank=True, null=True, config_name='extends')

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    sub_category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='sub_products', blank=True, null=True)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    store = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')

    price = models.DecimalField(max_digits=10, decimal_places=2)
    previous_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock_option = models.CharField(max_length=20, choices=STOCK_OPTION, default='Manual')
    quantity = models.PositiveIntegerField(default=0)
    inventory = models.ForeignKey(
        'inventory.Inventory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_inventory'
    )

    color = models.CharField(max_length=50, choices=COLOR_CHOICES, blank=True, null=True)
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, blank=True, null=True)
    weight = models.CharField(max_length=10, choices=WEIGHT_CHOICES, blank=True, null=True)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, blank=True, null=True)

    featured_image = models.ImageField(upload_to='products/featured/', blank=True, null=True)
    gallery_images = models.ManyToManyField('ProductImage', blank=True)

    meta_title = models.CharField(max_length=255, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    tags = models.CharField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        if not self.product_code:
            # Generate a unique product_code using a prefix and counter
            prefix = 'DK07'
            last_id = Product.objects.aggregate(last_id=Max('id'))['last_id'] or 0
            counter = last_id + 1
            # Add a short UUID segment for uniqueness in concurrent saves
            uuid_segment = str(uuid.uuid4())[:4].upper()
            self.product_code = f"{prefix}{counter:05d}-{uuid_segment}"
            # Ensure uniqueness
            while Product.objects.filter(product_code=self.product_code).exists():
                counter += 1
                self.product_code = f"{prefix}{counter:05d}-{uuid_segment}"

        if self.description:
            text = re.sub(r'<[^>]+>', '', self.description)
            words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
            unique_words = list(dict.fromkeys(words))
            self.tags = ', '.join(unique_words[:10])

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def is_in_stock(self):
        if self.stock_option == 'Manual':
            return self.quantity > 0
        return self.inventory.quantity > 0 if self.inventory else False

class ProductImage(models.Model):
    image = models.ImageField(upload_to='products/gallery/')
    alt_text = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.alt_text or f"Image {self.id}"
    


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField()
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Review by {self.user.username} for {self.product.name}"