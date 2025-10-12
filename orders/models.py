from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import User
from products.models import Product
from decimal import Decimal
from analytics.models import Customer
from products.models import COLOR_CHOICES, SIZE_CHOICES, WEIGHT_CHOICES

# Custom manager for Order model with useful querysets
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


from django.db import models
from django.conf import settings  # Import settings for AUTH_USER_MODEL
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

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

class Order(models.Model):
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

    # Basic Information - FIXED: Use settings.AUTH_USER_MODEL
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        related_name='orders'
    )
    
    # Customer relationship - FIXED
    customer = models.ForeignKey(
        'analytics.Customer',  # Replace 'analytics' with your actual app name
        on_delete=models.SET_NULL,
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
    
    # Customer Information (keep as CharField for direct storage)
    customer_name = models.CharField(max_length=100)
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
    
    # Attach the custom manager
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
            models.Index(fields=['customer']),  # Add index for customer
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            import uuid
            self.order_number = f"ORD-{uuid.uuid4().hex[:5].upper()}"
        
        if not self.total and self.subtotal:
            self.total = self.subtotal + self.tax_amount + self.shipping_cost - self.discount_amount
        
        # Auto-populate customer_name, email, phone from Customer if available
        if self.customer and not self.customer_name:
            self.customer_name = self.customer.name
        if self.customer and not self.email:
            self.email = self.customer.email
        if self.customer and not self.phone_number:
            self.phone_number = self.customer.phone
        
        super().save(*args, **kwargs)

    def calculate_totals(self):
        """Calculate and update all financial totals based on order items."""
        items = self.order_items.all()
        self.subtotal = sum(item.get_total() for item in items)
        self.total = self.subtotal + self.tax_amount + self.shipping_cost - self.discount_amount
        self.save()
        return self.total

    def __str__(self):
        return f"Order {self.order_number} - {self.customer_name} ({self.get_order_status_display()})"


class OrderItem(models.Model):
    DELIVERY_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('failed', 'Delivery Failed'),
        ('returned', 'Returned to Seller'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Product variants
    color = models.CharField(max_length=10,choices=COLOR_CHOICES, blank=True, null=True)
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, blank=True, null=True)
    weight = models.CharField(max_length=10, choices=WEIGHT_CHOICES, blank=True, null=True)
    delivery_status = models.CharField( max_length=20,choices=DELIVERY_STATUS_CHOICES,default='pending')
    # Additional item info
    item_note = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def get_total(self):
        price = self.price or 0
        quantity = self.quantity or 0
        return price * quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Order {self.order.order_number}"


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
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Bulk {self.get_operation_type_display()} - {self.name}"


