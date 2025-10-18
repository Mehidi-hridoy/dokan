# orders/models.py
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from users.models import User  # If needed elsewhere; otherwise removable

class OrderManager(models.Manager):
    def confirmed_orders(self):
        return self.filter(order_status='confirmed')
    
    def rejected_orders(self):
        return self.filter(order_status='rejected')
    
    def hold_orders(self):
        return self.filter(order_status='hold')
    
    def pending_orders(self):
        return self.filter(order_status='pending')
    
    def processed_orders(self):
        return self.filter(order_status='processed')
    
    def by_area(self, area):
        return self.filter(delivery_area=area)
    
    def recent_orders(self, days=30):
        from django.utils import timezone
        from datetime import timedelta
        return self.filter(created_at__gte=timezone.now()-timedelta(days=days))

# Order Status Choices
ORDER_STATUS_CHOICES = [
    ('confirmed', 'Confirmed'),
    ('rejected', 'Rejected'),
    ('hold', 'On Hold'),
    ('pending', 'Pending'),
    ('processed', 'Processed'),
]

# Courier Status Choices
COURIER_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('picked_up', 'Picked Up'),
    ('in_transit', 'In Transit'),
    ('out_for_delivery', 'Out for Delivery'),
    ('delivered', 'Delivered'),
    ('failed', 'Delivery Failed'),
    ('returned', 'Returned to Seller'),
]

# Payment Status Choices
PAYMENT_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('paid', 'Paid'),
    ('failed', 'Failed'),
    ('refunded', 'Refunded'),
    ('partially_refunded', 'Partially Refunded'),
]

PAYMENT_METHOD_CHOICES = [
    ('cod', 'Cash on Delivery'),
    ('card', 'Credit/Debit Card'),
    ('bank_transfer', 'Bank Transfer'),
    ('mobile_money', 'Mobile Money'),
    ('paypal', 'PayPal'),
    ('other', 'Other'),
]

class Order(models.Model):
    # Basic Information
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True,
        related_name='orders'
    )

    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_orders'
    )
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    courier_status = models.CharField(max_length=20, choices=COURIER_STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Financial Information
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Customer Information (keep as backup if customer is deleted)
    customer_name = models.CharField(max_length=100, blank=True, help_text='Insert customer name ')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    shipping_address = models.TextField(blank=True, null=True)
    billing_address = models.TextField(blank=True, null=True)
    
    # Additional Fields
    order_note = models.TextField(blank=True, null=True, help_text="Customer's order note")
    admin_comment = models.TextField(blank=True, null=True, help_text="Internal admin comments")
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
    
    # Area/Region Filtering
    delivery_area = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    zip_code = models.CharField(max_length=10, blank=True, null=True)
    
    # Courier Information
    courier_name = models.CharField(max_length=100, blank=True, null=True, help_text="Name of the courier service")
    courier_choice = models.CharField(
        max_length=50,
        choices=[
            ('pathao', 'Pathao'),
            ('red_x', 'Red X'),
            ('steadfast', 'Steadfast'),
        ],
        blank=True, 
        null=True,
        help_text="Select courier service"
    )
    tracking_number = models.CharField(max_length=100, blank=True, null=True, help_text="Tracking number provided by courier")
    estimated_delivery = models.DateField(blank=True, null=True, help_text="Estimated delivery date")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    
    objects = OrderManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_status']),
            models.Index(fields=['courier_status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['delivery_area']),
            models.Index(fields=['assigned_staff']),
            models.Index(fields=['user']),
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            import uuid
            self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        
        if not self.total and self.subtotal:
            self.total = self.subtotal + self.tax_amount + self.shipping_cost - self.discount_amount
        
        # Auto-populate customer information from Customer model if available
        if self.user:
            if not self.user_name:
                self.user_name = self.user.name
            if not self.email:
                self.email = self.user.email
            if not self.phone_number:
                self.phone_number = self.user.phone
        
        super().save(*args, **kwargs)

    def get_customer_display(self):
        """Get customer display name with fallback"""
        if self.user:
            return self.user.name  # Changed from display_name to name (safe)
        return self.user_name or "Unknown User"

    def __str__(self):
        return f"Order {self.order_number} - {self.user.get_full_name()} ({self.get_order_status_display()})"



class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.products_name} (x{self.quantity})"


class BulkOrderOperation(models.Model):
    """Model to track bulk order operations"""
    OPERATION_CHOICES = [
        ('status_update', 'Status Update'),
        ('courier_update', 'Courier Update'),
        ('area_filter', 'Area Filter'),
        ('export', 'Export Orders'),
        ('print', 'Print Labels'),
    ]
    
    name = models.CharField(max_length=100)
    operation_type = models.CharField(max_length=20, choices=OPERATION_CHOICES)
    filters_applied = models.JSONField(default=dict, blank=True)
    orders_affected = models.ManyToManyField(Order, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Bulk {self.get_operation_type_display()} - {self.name}"
    
