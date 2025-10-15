# analytics/models.py

from django.conf import settings
from django.db import models
from django.db.models import Count, Sum, F, Q, Min, Avg
from datetime import timedelta
from django.utils import timezone
from django.core.validators import RegexValidator
from decimal import Decimal

# --- Customer Manager (The Core Analytics Engine) ---

# analytics/models.py - UPDATED

from django.conf import settings
from django.db import models
from django.db.models import Count, Sum, F, Q, Min, Avg
from datetime import timedelta
from django.utils import timezone
from django.core.validators import RegexValidator
from decimal import Decimal

# Dynamic import of other app models needed by the CustomerManager
# NOTE: You must ensure 'products.Product' is a valid reference
try:
    from products.models import Product # Assuming Product is defined in a 'products' app
except ImportError:
    class Product(models.Model):
        class Meta:
            abstract = True
        # Placeholder to prevent crash if running makemigrations on a new setup.

# --- Customer Manager (The Core Analytics Engine) ---

class CustomerManager(models.Manager):
    """
    Manager to provide aggregated analytics for Customers and the entire business.
    """
    
    def _calculate_percentage_change(self, current, previous):
        # ... (Method remains unchanged)
        if previous == 0:
            return Decimal('100.00') if current > 0 else Decimal('0.00')
        return ((current - previous) / abs(previous) * 100).quantize(Decimal('0.01'))

    def get_customer_stats(self):
        # ... (Method remains unchanged)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        total_customers = self.all().count()
        new_customers = self.filter(first_order_date__gte=thirty_days_ago).count()
        regular_customers = self.filter(customer_type='regular').count() 
        vip_customers = self.filter(customer_type='vip').count()
        fraud_customers = self.filter(is_fraudulent=True).count()
        return {
            'new_customers': new_customers,
            'regular_customers': regular_customers,
            'vip_customers': vip_customers,
            'fraud_customers': fraud_customers,
            'total_customers': total_customers
        }
    
    def get_financial_overview(self, period_days=30):
        # ... (Logic remains largely unchanged)
        from orders.models import Order # Dynamic import
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        previous_start_date = start_date - timedelta(days=period_days)
        
        # ... (Filtering and aggregation for current/previous periods remain unchanged)
        current_orders = Order.objects.filter(
            created_at__gte=start_date, created_at__lte=end_date, payment_status='paid'
        )
        current_income = current_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')
        
        current_expenses = Expense.objects.filter(
            date__gte=start_date.date(), date__lte=end_date.date()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        current_damages = DamageReport.objects.filter(
            date_reported__gte=start_date, date_reported__lte=end_date
        ).aggregate(total=Sum('cost_amount'))['total'] or Decimal('0')
        
        # ... (Previous Period Data and Calculations remain unchanged)
        
        # ... (Return structure remains unchanged)
        return {
            'total_income': {'amount': current_income, 'change': income_change, 'previous': previous_income},
            'total_expenses': {'amount': total_current_expenses, 'change': expenses_change, 'previous': total_previous_expenses, 
                               'breakdown': {'operational': current_expenses, 'damages': current_damages}},
            'net_balance': {'amount': current_net, 'change': net_change, 'previous': previous_net},
            'savings_rate': {'amount': current_savings_rate, 'change': savings_rate_change, 'previous': previous_savings_rate},
            'period': {'current_start': start_date, 'current_end': end_date}
        }
    
    def get_sales_analytics(self, period_days=30):
        """Get detailed sales analytics: Orders, Top Products, Daily Trend."""
        from orders.models import Order, OrderItem # Dynamic import
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        
        # ... (Order statistics and Product performance remain unchanged)

        # 3. Daily sales trend - FIXED FOR SQLITE
        daily_sales = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
            payment_status='paid'
        ).extra({'date': "strftime('%%Y-%%m-%%d', created_at)"}).values('date').annotate(
            # Using strftime('%%Y-%%m-%%d', created_at) for daily grouping in SQLite
            daily_revenue=Sum('total'),
            order_count=Count('id')
        ).order_by('date')
        
        return {
            'orders': orders_data,
            'top_products': list(top_products),
            'daily_sales': list(daily_sales),
            'period': {'start': start_date, 'end': end_date}
        }

    def get_expense_analytics(self, period_days=30):
        """Get detailed expense analytics: By Category, Monthly Trend, Damages."""
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        
        # ... (Expense by category remains unchanged)

        # 2. Monthly expense trend (1 year lookback) - FIXED FOR SQLITE
        monthly_expenses = Expense.objects.filter(
            date__gte=start_date.date() - timedelta(days=365),
            date__lte=end_date.date()
        ).extra({'month': "strftime('%%Y-%%m', date)"}).values('month').annotate(
            # Using strftime('%%Y-%%m', date) for monthly grouping in SQLite
            monthly_total=Sum('amount')
        ).order_by('month')
        
        # ... (Damage analytics remains unchanged)
        
        return {
            'expenses_by_category': list(expenses_by_category),
            'monthly_expenses': list(monthly_expenses),
            'damage_analytics': damage_analytics,
            'period': {'start': start_date, 'end': end_date}
        }



# --- Customer Model (Data Storage for Analytics) ---

class Customer(models.Model):
    CUSTOMER_TYPES = (
        ('new', 'New Customer'),
        ('regular', 'Regular Customer'),
        ('vip', 'VIP Customer'),
        ('fraud', 'Fraud Customer'),
    )
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_profile', null=True, blank=True)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(
        max_length=15,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number is invalid.")]
    )
    
    avatar = models.ImageField(upload_to='customer_avatars/', blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPES, default='new')
    is_guest = models.BooleanField(default=False)
    is_fraudulent = models.BooleanField(default=False)
    
    total_orders = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    first_order_date = models.DateTimeField(null=True, blank=True)
    last_order_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = CustomerManager()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['customer_type']),
        ]
        
    def __str__(self):
        return f"{self.name} ({'Guest' if self.is_guest else 'Registered'})"
        
    def update_customer_stats(self):
        """Recalculates order counts, total spent, and updates customer type."""
        from orders.models import Order
        
        orders = Order.objects.filter(customer=self)
        # Use 'delivered' or 'confirmed' for completed orders based on your business logic.
        completed_orders = orders.filter(order_status='confirmed', payment_status='paid') 
        
        self.total_orders = completed_orders.count()
        self.total_spent = completed_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')
        
        first_order = completed_orders.order_by('created_at').first()
        last_order = completed_orders.order_by('-created_at').first()
        
        if first_order:
            self.first_order_date = first_order.created_at
        if last_order:
            self.last_order_date = last_order.created_at
        
        # Determine customer type
        if self.is_fraudulent:
            self.customer_type = 'fraud'
        elif self.total_orders >= 6 or self.total_spent >= Decimal('1000'):
            self.customer_type = 'vip'
        elif self.total_orders >= 2:
            self.customer_type = 'regular'
        else:
            self.customer_type = 'new'
            
        self.save()
        
    @property
    def status(self):
        return "Fraud" if self.is_fraudulent else "Active"
        
    @property
    def display_name(self):
        return self.name or "Walking Customer"

# --- Financial Records (For detailed financial tracking) ---

class FinancialRecord(models.Model):
    RECORD_TYPES = [
        ('sale', 'Sale'),
        ('refund', 'Refund'),
        ('damage', 'Damage/Loss'),
        ('expense', 'Expense'),
        ('shipping', 'Shipping Cost'),
        ('tax', 'Tax'),
        ('discount', 'Discount'),
        ('other', 'Other'),
    ]
    
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()
    reference = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        indexes = [models.Index(fields=['record_type']), models.Index(fields=['date'])]
        
    def __str__(self):
        return f"{self.get_record_type_display()} - ৳{self.amount} - {self.date.strftime('%Y-%m-%d')}"


# --- Expense Management Models ---

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#3498db', help_text="Hex color for charts")
    
    def __str__(self):
        return self.name

class Expense(models.Model):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()
    date = models.DateField(default=timezone.now)
    receipt = models.FileField(upload_to='expense_receipts/', blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        
    def __str__(self):
        return f"{self.category.name} - ৳{self.amount} - {self.date}"


# --- Damage & Loss Tracking Model ---

class DamageReport(models.Model):
    DAMAGE_TYPES = [
        ('shipping', 'Shipping Damage'),
        ('warehouse', 'Warehouse Damage'),
        ('manufacturing', 'Manufacturing Defect'),
        ('customer_return', 'Customer Return Damage'),
        ('other', 'Other'),
    ]
    
    # Assuming 'products.Product' is accessible
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE) 
    quantity = models.PositiveIntegerField()
    damage_type = models.CharField(max_length=20, choices=DAMAGE_TYPES)
    cost_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost value of damaged goods")
    sale_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Potential sale value if not damaged")
    description = models.TextField()
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    date_reported = models.DateTimeField(default=timezone.now)
    
    resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='resolved_damages')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date_reported']
        
    def __str__(self):
        # NOTE: Requires `product` to have `products_name` field
        return f"Damage - {self.product.products_name} - {self.quantity} units - ৳{self.cost_amount}"