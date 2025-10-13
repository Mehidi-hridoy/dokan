from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import User
from products.models import Product
from decimal import Decimal
from analytics.models import Customer
from products.models import COLOR_CHOICES, SIZE_CHOICES, WEIGHT_CHOICES
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver

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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        related_name='orders'
    )
    
    # Customer relationship - This is the main customer link
    customer = models.ForeignKey(
        'analytics.Customer',
        on_delete=models.CASCADE,  # Changed to CASCADE to maintain data integrity
        null=True,
        blank=True,
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
    customer_name = models.CharField(max_length=100, blank=True)
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
            models.Index(fields=['customer']),
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            import uuid
            self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        
        if not self.total and self.subtotal:
            self.total = self.subtotal + self.tax_amount + self.shipping_cost - self.discount_amount
        
        # Auto-populate customer information from Customer model if available
        if self.customer:
            if not self.customer_name:
                self.customer_name = self.customer.name
            if not self.email:
                self.email = self.customer.email
            if not self.phone_number:
                self.phone_number = self.customer.phone
        
        super().save(*args, **kwargs)
        
        # Sync order items status when order status changes
        if 'update_fields' not in kwargs or 'order_status' in kwargs.get('update_fields', []):
            self.sync_order_items_status()

    def sync_order_items_status(self):
        """Sync order status to all order items"""
        self.order_items.all().update(
            order_status=self.order_status,
            courier_status=self.courier_status
        )

    def calculate_totals(self):
        """Calculate and update all financial totals based on order items."""
        items = self.order_items.all()
        self.subtotal = sum(item.get_total() for item in items)
        self.total = self.subtotal + self.tax_amount + self.shipping_cost - self.discount_amount
        self.save()
        return self.total

    def get_customer_display(self):
        """Get customer display name with fallback"""
        if self.customer:
            return self.customer.display_name
        return self.customer_name or "Unknown Customer"

    def __str__(self):
        return f"Order {self.order_number} - {self.get_customer_display()} ({self.get_order_status_display()})"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    customer = models.ForeignKey(
        'analytics.Customer', 
        on_delete=models.CASCADE, 
        related_name='order_items',
        null=True, 
        blank=True
    )
    
    # Product information (immutable after order creation)
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)  # PROTECT to prevent deletion if ordered
    product_name = models.CharField(max_length=255, blank=True)  # Store product name at time of order
    product_code = models.CharField(max_length=20, blank=True)  # Store product code at time of order
    
    # Pricing (immutable - captured at time of order)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at time of order")
    original_unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Original product price without promotions")
    
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    
    # Product variants (captured at time of order)
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, blank=True, null=True)
    weight = models.CharField(max_length=10, choices=WEIGHT_CHOICES, blank=True, null=True)
    
    # Promotion information
    promotion_applied = models.BooleanField(default=False)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=50, blank=True, null=True)
    
    # Status fields
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    courier_status = models.CharField(max_length=20, choices=COURIER_STATUS_CHOICES, default='pending')
    
    # Additional info
    item_note = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Capture product information at time of creation
        if not self.pk and self.product:
            self.product_name = self.product.products_name
            self.product_code = self.product.product_code
            self.original_unit_price = self.product.current_price
            
            # If unit_price is not set, use current product price
            if not self.unit_price:
                self.unit_price = self.product.current_price
        
        # Auto-populate customer from order
        if not self.customer and self.order and self.order.customer:
            self.customer = self.order.customer
        
        super().save(*args, **kwargs)

    def get_total(self):
        """Calculate total price for this order item (immutable)"""
        return (self.unit_price or 0) * (self.quantity or 0)

    def get_total_before_discount(self):
        """Calculate total before any promotions"""
        return (self.original_unit_price or 0) * (self.quantity or 0)

    def get_discount_savings(self):
        """Calculate discount savings"""
        return self.get_total_before_discount() - self.get_total()

    def __str__(self):
        return f"{self.quantity} x {self.product_name} @ ${self.unit_price}"


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


# Signal handlers to maintain data consistency
@receiver(post_save, sender=Order)
def update_order_items_on_order_save(sender, instance, **kwargs):
    """
    Update all order items when order status changes
    """
    # This is handled in the Order.save() method now
    pass

@receiver(post_save, sender=OrderItem)
def update_order_totals_on_item_save(sender, instance, **kwargs):
    """
    Update order totals when order items are saved
    """
    if instance.order:
        instance.order.calculate_totals()