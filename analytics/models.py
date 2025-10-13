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


# analytics/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.core.validators import RegexValidator

# Add these new models at the top of your existing models
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
        indexes = [
            models.Index(fields=['record_type']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.get_record_type_display()} - ৳{self.amount} - {self.date.strftime('%Y-%m-%d')}"

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#3498db')
    
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

class DamageReport(models.Model):
    DAMAGE_TYPES = [
        ('shipping', 'Shipping Damage'),
        ('warehouse', 'Warehouse Damage'),
        ('manufacturing', 'Manufacturing Defect'),
        ('customer_return', 'Customer Return Damage'),
        ('other', 'Other'),
    ]
    
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
        return f"Damage - {self.product.products_name} - {self.quantity} units - ৳{self.cost_amount}"

# Your existing CustomerManager class - UPDATE IT with financial methods
class CustomerManager(models.Manager):
    def get_customer_stats(self):
        """Get customer statistics for dashboard"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        total_customers = self.all().count()
        new_customers = self.filter(first_order_date__gte=thirty_days_ago).count()
        regular_customers = self.filter(total_orders__gte=2, total_orders__lte=5).count()
        vip_customers = self.filter(total_orders__gte=6).count()
        fraud_customers = self.filter(is_fraudulent=True).count()
        
        return {
            'new_customers': new_customers,
            'regular_customers': regular_customers,
            'vip_customers': vip_customers,
            'fraud_customers': fraud_customers,
            'total_customers': total_customers
        }
    
    def get_financial_overview(self, period_days=30):
        """Get comprehensive financial overview for analytics"""
        from django.db.models import Sum, Count, Q
        from orders.models import Order
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        previous_start_date = start_date - timedelta(days=period_days)
        
        # Current period data
        current_orders = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
            payment_status='paid'
        )
        
        # Previous period data
        previous_orders = Order.objects.filter(
            created_at__gte=previous_start_date,
            created_at__lt=start_date,
            payment_status='paid'
        )
        
        # Sales calculations
        current_income = current_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')
        previous_income = previous_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')
        
        # Expense calculations
        current_expenses = Expense.objects.filter(
            date__gte=start_date.date(),
            date__lte=end_date.date()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        previous_expenses = Expense.objects.filter(
            date__gte=previous_start_date.date(),
            date__lt=start_date.date()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Damage calculations
        current_damages = DamageReport.objects.filter(
            date_reported__gte=start_date,
            date_reported__lte=end_date
        ).aggregate(total=Sum('cost_amount'))['total'] or Decimal('0')
        
        previous_damages = DamageReport.objects.filter(
            date_reported__gte=previous_start_date,
            date_reported__lt=start_date
        ).aggregate(total=Sum('cost_amount'))['total'] or Decimal('0')
        
        # Total expenses (operational expenses + damages)
        total_current_expenses = current_expenses + current_damages
        total_previous_expenses = previous_expenses + previous_damages
        
        # Net balance
        current_net = current_income - total_current_expenses
        previous_net = previous_income - total_previous_expenses
        
        # Savings rate (Net Income / Total Income)
        current_savings_rate = (current_net / current_income * 100) if current_income > 0 else Decimal('0')
        previous_savings_rate = (previous_net / previous_income * 100) if previous_income > 0 else Decimal('0')
        
        # Calculate percentage changes
        income_change = self._calculate_percentage_change(current_income, previous_income)
        expenses_change = self._calculate_percentage_change(total_current_expenses, total_previous_expenses)
        net_change = self._calculate_percentage_change(current_net, previous_net)
        savings_rate_change = self._calculate_percentage_change(current_savings_rate, previous_savings_rate)
        
        return {
            'total_income': {
                'amount': current_income,
                'change': income_change,
                'previous': previous_income
            },
            'total_expenses': {
                'amount': total_current_expenses,
                'change': expenses_change,
                'previous': total_previous_expenses,
                'breakdown': {
                    'operational': current_expenses,
                    'damages': current_damages
                }
            },
            'net_balance': {
                'amount': current_net,
                'change': net_change,
                'previous': previous_net
            },
            'savings_rate': {
                'amount': current_savings_rate,
                'change': savings_rate_change,
                'previous': previous_savings_rate
            },
            'period': {
                'current_start': start_date,
                'current_end': end_date,
                'previous_start': previous_start_date,
                'previous_end': start_date - timedelta(days=1)
            }
        }
    
    def _calculate_percentage_change(self, current, previous):
        """Calculate percentage change between current and previous values"""
        if previous == 0:
            return Decimal('100.00') if current > 0 else Decimal('0.00')
        return ((current - previous) / abs(previous) * 100).quantize(Decimal('0.01'))
    
    def get_sales_analytics(self, period_days=30):
        """Get detailed sales analytics"""
        from orders.models import Order, OrderItem
        from django.db.models import Count, Sum, Avg
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        
        # Order statistics
        orders_data = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).aggregate(
            total_orders=Count('id'),
            completed_orders=Count('id', filter=Q(order_status='delivered')),
            total_revenue=Sum('total', filter=Q(payment_status='paid')),
            avg_order_value=Avg('total', filter=Q(payment_status='paid'))
        )
        
        # Product performance
        top_products = OrderItem.objects.filter(
            order__created_at__gte=start_date,
            order__created_at__lte=end_date,
            order__payment_status='paid'
        ).values(
            'product__products_name',
            'product__product_code'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('unit_price') * Sum('quantity')
        ).order_by('-total_revenue')[:10]
        
        # Daily sales trend
        daily_sales = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
            payment_status='paid'
        ).extra({
            'date': "DATE(created_at)"
        }).values('date').annotate(
            daily_revenue=Sum('total'),
            order_count=Count('id')
        ).order_by('date')
        
        return {
            'orders': orders_data,
            'top_products': list(top_products),
            'daily_sales': list(daily_sales),
            'period': {
                'start': start_date,
                'end': end_date
            }
        }
    
    def get_expense_analytics(self, period_days=30):
        """Get detailed expense analytics"""
        from django.db.models import Sum
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        
        # Expense by category
        expenses_by_category = Expense.objects.filter(
            date__gte=start_date.date(),
            date__lte=end_date.date()
        ).values('category__name', 'category__color').annotate(
            total=Sum('amount')
        ).order_by('-total')
        
        # Monthly expense trend
        monthly_expenses = Expense.objects.filter(
            date__gte=start_date.date() - timedelta(days=365),
            date__lte=end_date.date()
        ).extra({
            'month': "DATE_FORMAT(date, '%%Y-%%m')"
        }).values('month').annotate(
            monthly_total=Sum('amount')
        ).order_by('month')
        
        # Damage analytics
        damage_analytics = DamageReport.objects.filter(
            date_reported__gte=start_date,
            date_reported__lte=end_date
        ).aggregate(
            total_damages=Sum('cost_amount'),
            total_units=Sum('quantity'),
            avg_damage_cost=Avg('cost_amount')
        )
        
        return {
            'expenses_by_category': list(expenses_by_category),
            'monthly_expenses': list(monthly_expenses),
            'damage_analytics': damage_analytics,
            'period': {
                'start': start_date,
                'end': end_date
            }
        }

# Your existing Customer model remains the same
class Customer(models.Model):
    CUSTOMER_TYPES = (
        ('new', 'New Customer'),
        ('regular', 'Regular Customer'),
        ('vip', 'VIP Customer'),
        ('fraud', 'Fraud Customer'),
    )
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, 
        related_name='customer_profile',
        null=True,
        blank=True
    )
    
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
            models.Index(fields=['is_guest']),
            models.Index(fields=['customer_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({'Guest' if self.is_guest else 'Registered'})"
    
    def update_customer_stats(self):
        from orders.models import Order
        
        orders = Order.objects.filter(customer=self)
        completed_orders = orders.filter(order_status='confirmed')
        
        self.total_orders = completed_orders.count()
        self.total_spent = completed_orders.aggregate(
            total=Sum('total')
        )['total'] or 0
        
        first_order = orders.order_by('created_at').first()
        last_order = orders.order_by('-created_at').first()
        
        if first_order:
            self.first_order_date = first_order.created_at
        if last_order:
            self.last_order_date = last_order.created_at
        
        if self.total_orders >= 6 or self.total_spent >= 1000:
            self.customer_type = 'vip'
        elif self.total_orders >= 2:
            self.customer_type = 'regular'
        else:
            self.customer_type = 'new'
            
        self.save()
    
    @property
    def status(self):
        if self.is_fraudulent:
            return "Fraud"
        return "Active"
    
    @property
    def display_name(self):
        return self.name or "Walking Customer"