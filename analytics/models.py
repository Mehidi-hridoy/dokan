from django.db import models
from django.conf import settings
from django.db.models import Count, Sum, F, Q, Min
from datetime import timedelta
from django.utils import timezone
from django.core.validators import RegexValidator

class CustomerManager(models.Manager):
    def get_customer_stats(self):
        """Get customer statistics for dashboard"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Total customers (both registered and guest)
        total_customers = self.all().count()
        
        # Get customer type counts based on order ranges
        new_customers = self.filter(
            total_orders__gte=0,
            total_orders__lte=5
        ).count()
        
        regular_customers = self.filter(
            total_orders__gte=6,
            total_orders__lte=15
        ).count()
        
        vip_customers = self.filter(
            total_orders__gte=10,
            total_orders__lte=20
        ).count()
        
        # Customers who qualify for multiple categories (overlap handling)
        overlap_vip_regular = self.filter(
            total_orders__gte=10,
            total_orders__lte=15
        ).count()
        
        # Adjust counts to avoid double counting
        if overlap_vip_regular > 0:
            # In case of overlap, prioritize VIP
            regular_customers -= overlap_vip_regular
        
        # Fraud customers
        fraud_customers = self.filter(is_fraudulent=True).count()
        
        return {
            'new_customers': new_customers,
            'regular_customers': regular_customers,
            'vip_customers': vip_customers,
            'fraud_customers': fraud_customers,
            'total_customers': total_customers
        }
    
    def get_customer_type_by_orders(self, order_count):
        """Determine customer type based on order count"""
        if 0 <= order_count <= 5:
            return 'new'
        elif 6 <= order_count <= 15:
            return 'regular'
        elif 10 <= order_count <= 20:
            return 'vip'
        else:
            # For orders above 20, keep as VIP
            return 'vip'
    
    def get_or_create_guest_customer(self, email, phone, name):
        """Get or create a customer for guest checkout"""
        # Try to find existing customer by email or phone
        customer = self.filter(
            Q(email=email) | Q(phone=phone)
        ).first()
        
        if customer:
            return customer, False
        
        # Create new guest customer
        customer = self.create(
            email=email,
            phone=phone,
            name=name,
            is_guest=True
        )
        return customer, True

class Customer(models.Model):
    
    CUSTOMER_TYPES = (
        ('new', 'New Customer (0-5 orders)'),
        ('regular', 'Regular Customer (6-15 orders)'),
        ('vip', 'VIP Customer (10-20 orders)'),
        ('fraud', 'Fraud Customer'),
    )
    
    # Link to User model (optional - for registered users)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, 
        related_name='customer_profile',
        null=True,
        blank=True
    )
    
    # Customer information (for both guest and registered users)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ]
    )
    
    # Additional fields
    avatar = models.ImageField(upload_to='customer_avatars/', blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPES, default='new')
    is_guest = models.BooleanField(default=False)
    is_fraudulent = models.BooleanField(default=False)
    
    # Statistics
    total_orders = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    first_order_date = models.DateTimeField(null=True, blank=True)
    last_order_date = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = CustomerManager()
    
    class Meta:
        verbose_name = "Customers"
        verbose_name_plural = "Customers List"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['is_guest']),
            models.Index(fields=['customer_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({'Guest' if self.is_guest else 'Registered'})"
    
    def update_customer_stats(self):
        """Update customer statistics based on order history"""
        # Import here to avoid circular imports
        from orders.models import Order
        
        orders = Order.objects.filter(customer=self)
        completed_orders = orders.filter(order_status='confirmed')
        
        self.total_orders = completed_orders.count()
        self.total_spent = completed_orders.aggregate(
            total=Sum('total')
        )['total'] or 0
        
        # Update first and last order dates
        first_order = orders.order_by('created_at').first()
        last_order = orders.order_by('-created_at').first()
        
        if first_order:
            self.first_order_date = first_order.created_at
        if last_order:
            self.last_order_date = last_order.created_at
        
        # Update customer type based on the new order ranges
        self.customer_type = Customer.objects.get_customer_type_by_orders(self.total_orders)
            
        self.save()
    
    @property
    def status(self):
        if self.is_fraudulent:
            return "Fraud"
        return "Active"
    
    @property
    def display_name(self):
        return self.name or "Walking Customer"
    
    @property
    def order_range(self):
        """Return the order range for the customer type"""
        if self.customer_type == 'new':
            return "0-5 orders"
        elif self.customer_type == 'regular':
            return "6-15 orders"
        elif self.customer_type == 'vip':
            return "10-20 orders"
        else:
            return "N/A"
        