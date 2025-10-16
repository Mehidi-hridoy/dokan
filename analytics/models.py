# analytics/models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from inventory.models import Inventory
from products.models import Product

User = get_user_model()  # Reference to your User model (e.g., from users.app)

class Customer(models.Model):
    user = models.OneToOneField(
        'users.User',  # String reference to your users app
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_profile'
    )    
    # Basic Info
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Address (for order history and segmentation)
    shipping_address = models.TextField(blank=True, null=True)
    billing_address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, default='BD')  # Assuming Bangladesh; customize
    
    # Analytics Aggregates (cached for performance)
    total_orders = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['total_spent']),  # For high-value customer reports
        ]
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return self.name or self.email

    def get_lifetime_value(self):
        """Return total spent (or from related orders)."""
        return self.total_spent

    def update_aggregates(self):
        """Recalculate from orders (call in signals)."""
        aggregates = self.orders.aggregate(
            order_count=models.Count('id'),
            spent_sum=models.Sum('total')
        )
        self.total_orders = aggregates['order_count'] or 0
        self.total_spent = aggregates['spent_sum'] or 0
        self.save(update_fields=['total_orders', 'total_spent'])
# inventory/models.py
from django.db import models

class Inventory(models.Model):
    # Reverse OneToOne from Product with explicit related_name
    product = models.OneToOneField(
        'products.Product',  # String reference
        on_delete=models.CASCADE,
        related_name='inventory_record'  # NEW: Overrides reverse from Product.inventory -> avoids clash with 'inventory' field in Product
    )
    
    # ... rest of your fields (quantity, reserved_quantity, etc.) ...
    
    # ... methods like available_quantity ...
# Existing AnalyticsSnapshot model (unchanged)
class AnalyticsSnapshot(models.Model):
    """Optional: Cache daily aggregates for performance."""
    date = models.DateField(default=timezone.now, unique=True)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    low_stock_count = models.PositiveIntegerField(default=0)
    out_of_stock_count = models.PositiveIntegerField(default=0)
    top_product_sales = models.JSONField(default=dict)  # e.g., {'product_id': sales_count}

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Snapshot {self.date} - Revenue: {self.total_revenue}"