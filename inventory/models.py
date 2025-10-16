# inventory/models.py
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError
from products.models import Product  

class InventoryManager(models.Manager):
    def low_stock(self):
        """Return inventory items with low stock (excluding out-of-stock)"""
        return self.filter(
            quantity__gt=0,
            quantity__lte=models.F('low_stock_threshold')
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
    product = models.OneToOneField(
        'products.Product',  # String
        on_delete=models.CASCADE,
        related_name='inventory_reverse'  # Explicit to avoid clashes
    )
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0, help_text="Quantity reserved for pending orders")
    location = models.CharField(max_length=100, blank=True, null=True)
    batch_number = models.CharField(max_length=50, blank=True, null=True, help_text="Batch/Lot number for traceability")
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
            models.Index(fields=['batch_number']),
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

    def reserve_stock(self, quantity, reference="Order Reserve"):
        """Reserve stock for an order and log movement"""
        if self.available_quantity >= quantity:
            self.reserved_quantity += quantity
            self.save()
            StockMovement.objects.create(
                inventory=self,
                movement_type='out',  # Reserved as 'out' from available
                quantity=-quantity,  # Negative for reservation
                reference=reference,
                note="Reserved for order"
            )
            return True
        return False

    def release_reservation(self, quantity, reference="Order Cancel"):
        """Release reserved stock"""
        if self.reserved_quantity >= quantity:
            self.reserved_quantity -= quantity
            self.save()
            StockMovement.objects.create(
                inventory=self,
                movement_type='return',
                quantity=quantity,
                reference=reference,
                note="Reservation released"
            )

    def consume_stock(self, quantity, reference="Order Consume"):
        """Consume reserved stock (for completed orders)"""
        if self.reserved_quantity >= quantity:
            self.reserved_quantity -= quantity
            self.quantity = max(0, self.quantity - quantity)
            self.save()
            StockMovement.objects.create(
                inventory=self,
                movement_type='out',
                quantity=-quantity,
                reference=reference,
                note="Stock consumed"
            )

    def add_stock(self, quantity, created_by=None, reference="Restock"):
        """Add stock to inventory and log"""
        self.quantity += quantity
        self.last_restocked = timezone.now()
        self.save()
        StockMovement.objects.create(
            inventory=self,
            movement_type='in',
            quantity=quantity,
            reference=reference,
            note="Stock added",
            created_by=created_by
        )

    def reserve_for_order(self, order, items_qty_dict):
        """Placeholder: Reserve based on order items (extend with OrderItem later)"""
        total_qty = sum(items_qty_dict.values())
        return self.reserve_stock(total_qty, reference=f"Order {order.order_number}")

class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('return', 'Return'),
        ('damaged', 'Damaged'),  # Fixed typo
    ]
    
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(help_text="Positive for in/return, negative for out/damaged")
    reference = models.CharField(max_length=100, blank=True, null=True, help_text="Order number, adjustment reason, etc.")
    note = models.TextField(blank=True, null=True)
    
    # Automatically track stock levels
    previous_quantity = models.PositiveIntegerField(editable=False)
    new_quantity = models.PositiveIntegerField(editable=False)
    
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['movement_type']),
            models.Index(fields=['created_at']),
        ]

    def clean(self):
        """Validate quantity sign based on type"""
        if self.movement_type in ['in', 'return'] and self.quantity <= 0:
            raise ValidationError("Quantity must be positive for 'in' or 'return'.")
        if self.movement_type in ['out', 'damaged'] and self.quantity >= 0:
            raise ValidationError("Quantity must be negative for 'out' or 'damaged'.")

    def save(self, *args, **kwargs):
        self.clean()
        
        if not self.pk:
            self.previous_quantity = self.inventory.quantity  # Snapshot before change
            
            # Apply changes
            if self.movement_type == 'in':
                self.inventory.quantity += abs(self.quantity)
            elif self.movement_type == 'return':
                self.inventory.quantity += abs(self.quantity)
            elif self.movement_type == 'out':
                self.inventory.quantity = max(0, self.inventory.quantity - abs(self.quantity))
            elif self.movement_type == 'damaged':
                self.inventory.quantity = max(0, self.inventory.quantity - abs(self.quantity))
            
            self.inventory.save()
            self.new_quantity = self.inventory.quantity
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_movement_type_display()} - {abs(self.quantity)} units - {self.inventory.product.products_name}"

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
    resolved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    
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

    def resolve(self, user=None):
        """Mark alert as resolved"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.save()

# Signals
@receiver(post_save, sender=Product)
def create_inventory_for_product(sender, instance, created, **kwargs):
    """Automatically create inventory record when a new product is created"""
    if created:
        Inventory.objects.get_or_create(product=instance)

@receiver(post_save, sender=StockMovement)
def trigger_stock_alert(sender, instance, created, **kwargs):
    """Create alert if movement causes low/out stock"""
    if created:
        inv = instance.inventory
        if inv.is_low_stock:
            StockAlert.objects.create(
                inventory=inv,
                alert_type='low_stock',
                message=f"Low stock for {inv.product.products_name}: {inv.available_quantity} left."
            )
        elif inv.is_stock_out:
            StockAlert.objects.create(
                inventory=inv,
                alert_type='out_of_stock',
                message=f"Out of stock for {inv.product.products_name}."
            )