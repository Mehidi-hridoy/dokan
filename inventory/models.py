from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

class InventoryManager(models.Manager):
    def low_stock(self):
        """Return inventory items with low stock"""
        return self.filter(
            quantity__lte=models.F('low_stock_threshold'),
            quantity__gt=5
        )
    
    def out_of_stock(self):
        """Return out of stock items"""
        return self.filter(quantity=0)
    
    def in_stock(self):
        """Return items with available stock"""
        return self.filter(quantity__gt=0)
    
    def by_location(self, location):
        """Return inventory items by location"""
        return self.filter(location=location)

class Inventory(models.Model):
    product = models.OneToOneField( 'products.Product', on_delete=models.CASCADE, related_name='inventory')
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0, help_text="Quantity reserved for pending orders")
    location = models.CharField(max_length=100, blank=True, null=True)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    reorder_quantity = models.PositiveIntegerField(default=10, help_text="Quantity to reorder when stock is low")
    
    # Tracking
    last_restocked = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = InventoryManager()

    class Meta:
        verbose_name = "Inventory"
        verbose_name_plural = "Inventories"
        indexes = [
            models.Index(fields=['quantity']),
            models.Index(fields=['location']),
        ]

    def __str__(self):
        return f"{self.product.products_name} - {self.available_quantity} available"

    @property
    def available_quantity(self):
        """Get available quantity (total minus reserved)"""
        return max(0, self.quantity - self.reserved_quantity)

    @property
    def is_stock_out(self):
        """Check if completely out of stock"""
        return self.available_quantity == 0

    @property
    def is_low_stock(self):
        """Check if stock is low"""
        return 0 < self.available_quantity <= self.low_stock_threshold

    @property
    def needs_restock(self):
        """Check if needs restocking"""
        return self.is_low_stock or self.is_stock_out

    def reserve_stock(self, quantity):
        """Reserve stock for an order"""
        if self.available_quantity >= quantity:
            self.reserved_quantity += quantity
            self.save()
            return True
        return False

    def release_stock(self, quantity):
        """Release reserved stock"""
        self.reserved_quantity = max(0, self.reserved_quantity - quantity)
        self.save()

    def consume_stock(self, quantity):
        """Consume stock (for completed orders)"""
        if self.reserved_quantity >= quantity:
            self.reserved_quantity -= quantity
        self.quantity = max(0, self.quantity - quantity)
        self.save()

    def add_stock(self, quantity):
        """Add stock to inventory"""
        self.quantity += quantity
        self.last_restocked = timezone.now()
        self.save()


class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjustment', 'Adjustment'),
        ('return', 'Return'),
        ('reserved', 'Reserved'),
        ('released', 'Released'),
    ]
    
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(help_text="Positive for in, negative for out")
    reference = models.CharField(max_length=100, blank=True, null=True, help_text="Order number, adjustment reason, etc.")
    note = models.TextField(blank=True, null=True)
    
    # Automatically track stock levels
    previous_quantity = models.PositiveIntegerField(editable=False)
    new_quantity = models.PositiveIntegerField(editable=False)
    
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Only set previous_quantity when creating a new record
        if not self.pk:
            self.previous_quantity = self.inventory.available_quantity

            # Apply stock changes
            if self.movement_type in ['in', 'return', 'adjustment']:
                self.inventory.quantity += self.quantity
            elif self.movement_type in ['out']:
                self.inventory.quantity = max(0, self.inventory.quantity - self.quantity)
            elif self.movement_type == 'reserved':
                self.inventory.reserved_quantity += self.quantity
            elif self.movement_type == 'released':
                self.inventory.reserved_quantity = max(0, self.inventory.reserved_quantity - self.quantity)

            # Save inventory changes
            self.inventory.save()

            # Set new quantity after update
            self.new_quantity = self.inventory.available_quantity

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.quantity} units - {self.inventory.product.products_name}"



class StockAlert(models.Model):
    ALERT_TYPES = [
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('over_stock', 'Over Stock'),
    ]
    
    ALERT_STATUS = [
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=ALERT_STATUS, default='active')
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['alert_type']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.inventory.product.products_name}"

    def resolve(self):
        """Mark alert as resolved"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.save()


# Signals
@receiver(post_save, sender='products.Product')
def create_inventory_for_product(sender, instance, created, **kwargs):
    """Automatically create inventory record when a new product is created"""
    if created:
        from .models import Inventory
        Inventory.objects.get_or_create(product=instance)