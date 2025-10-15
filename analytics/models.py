from django.conf import settings
from django.db.models import Count, Sum, F, Q, Min, Avg
from datetime import timedelta
from django.utils import timezone
from django.core.validators import RegexValidator
from django.db import models
from decimal import Decimal
from django.db.models.functions import TruncMonth, TruncDate
from django.db import connection
import datetime
import datetime
from datetime import datetime, date, time, timedelta

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
        from orders.models import Order
        from .models import Expense, DamageReport
        
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
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        
        # Order statistics
        orders_data = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).aggregate(
            total_orders=Count('id'),
            completed_orders=Count('id', filter=Q(order_status='confirmed')),
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
            total_revenue=Sum(F('unit_price') * F('quantity'))
        ).order_by('-total_revenue')[:10]
        
        # Daily sales trend - Database agnostic approach
        daily_sales = []
        for i in range(period_days):
            date = end_date - timedelta(days=i)
            day_start = timezone.make_aware(datetime.combine(date.date(), datetime.min.time()))
            day_end = timezone.make_aware(datetime.combine(date.date(), datetime.max.time()))
            
            daily_revenue = Order.objects.filter(
                created_at__gte=day_start,
                created_at__lte=day_end,
                payment_status='paid'
            ).aggregate(total=Sum('total'))['total'] or Decimal('0')
            
            daily_sales.append({
                'date': date.date(),
                'daily_revenue': daily_revenue
            })
        
        daily_sales.reverse()  # Sort chronologically
        
        return {
            'orders': orders_data,
            'top_products': list(top_products),
            'daily_sales': daily_sales,
            'period': {
                'start': start_date,
                'end': end_date
            }
        }

    def get_expense_analytics(self, period_days=30):
        """Get detailed expense analytics"""
        from django.db.models import Sum
        from datetime import datetime
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        
        # Expense by category
        expenses_by_category = Expense.objects.filter(
            date__gte=start_date.date(),
            date__lte=end_date.date()
        ).values('category__name', 'category__color').annotate(
            total=Sum('amount')
        ).order_by('-total')
        
        # Monthly expense trend - Database agnostic approach
        monthly_expenses = []
        for i in range(12):
            month_date = end_date - timedelta(days=30*i)
            month_start = timezone.make_aware(datetime(month_date.year, month_date.month, 1))
            if month_date.month == 12:
                month_end = timezone.make_aware(datetime(month_date.year + 1, 1, 1)) - timedelta(days=1)
            else:
                month_end = timezone.make_aware(datetime(month_date.year, month_date.month + 1, 1)) - timedelta(days=1)
            
            monthly_total = Expense.objects.filter(
                date__gte=month_start.date(),
                date__lte=month_end.date()
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            monthly_expenses.append({
                'month': month_start.strftime('%Y-%m'),
                'monthly_total': monthly_total
            })
        
        monthly_expenses.reverse()  # Sort chronologically
        
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
            'monthly_expenses': monthly_expenses,
            'damage_analytics': damage_analytics,
            'period': {
                'start': start_date,
                'end': end_date
            }
        }

    def get_inventory_analytics(self):
        """Get inventory analytics"""
        from inventory.models import Inventory, StockAlert
        
        inventory_stats = Inventory.objects.aggregate(
            total_products=Count('id'),
            in_stock=Count('id', filter=Q(quantity__gt=0)),
            low_stock=Count('id', filter=Q(quantity__lte=F('low_stock_threshold'), quantity__gt=0)),
            out_of_stock=Count('id', filter=Q(quantity=0)),
            total_inventory_value=Sum(
                F('quantity') * 
                Case(
                    When(product__sale_price__isnull=False, then=F('product__sale_price')),
                    default=F('product__base_price'),
                    output_field=models.DecimalField()
                )
            )
        )
        
        # Recent stock alerts
        recent_alerts = StockAlert.objects.filter(status='active').select_related('inventory__product')[:5]
        
        # Low stock products
        low_stock_products = Inventory.objects.filter(
            quantity__lte=F('low_stock_threshold'),
            quantity__gt=0
        ).select_related('product')[:10]
        
        return {
            'inventory_stats': inventory_stats,
            'recent_alerts': recent_alerts,
            'low_stock_products': low_stock_products,
            'active_alert_count': StockAlert.objects.filter(status='active').count()
        }

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
        )['total'] or Decimal('0')
        
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

class AnalyticsSnapshot(models.Model):
    """Store periodic analytics snapshots for trend analysis"""
    SNAPSHOT_TYPES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    snapshot_type = models.CharField(max_length=10, choices=SNAPSHOT_TYPES)
    snapshot_date = models.DateField()
    
    # Key metrics
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.IntegerField(default=0)
    new_customers = models.IntegerField(default=0)
    total_products_sold = models.IntegerField(default=0)
    avg_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Inventory metrics
    total_inventory_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    low_stock_items = models.IntegerField(default=0)
    out_of_stock_items = models.IntegerField(default=0)
    
    # Customer metrics
    customer_acquisition_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    customer_lifetime_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-snapshot_date', '-snapshot_type']
        unique_together = ['snapshot_type', 'snapshot_date']
        indexes = [
            models.Index(fields=['snapshot_type', 'snapshot_date']),
        ]
    
    def __str__(self):
        return f"{self.get_snapshot_type_display()} Snapshot - {self.snapshot_date}"

class ProductPerformance(models.Model):
    """Track product performance over time"""
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    period_date = models.DateField()
    
    # Performance metrics
    units_sold = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    order_count = models.PositiveIntegerField(default=0)
    avg_selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Inventory metrics
    starting_stock = models.PositiveIntegerField(default=0)
    ending_stock = models.PositiveIntegerField(default=0)
    stock_turnover = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-period_date', '-total_revenue']
        unique_together = ['product', 'period_date']
        indexes = [
            models.Index(fields=['product', 'period_date']),
            models.Index(fields=['period_date', 'total_revenue']),
        ]
    
    def __str__(self):
        return f"{self.product.products_name} - {self.period_date}"

# Import Case and When for inventory calculations
from django.db.models import Case, When

# Signal to update customer stats when order is saved
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender='orders.Order')
def update_customer_on_order_save(sender, instance, **kwargs):
    """
    Update customer statistics when an order is saved.
    If no linked customer exists, try to find or create a guest customer.
    """
    if instance.customer:
        instance.customer.update_customer_stats()
    elif instance.email and instance.phone_number:
        customer, created = Customer.objects.get_or_create(
            email=instance.email,
            defaults={
                'phone': instance.phone_number,
                'name': instance.customer_name or "Guest Customer",
                'is_guest': True
            }
        )
        instance.customer = customer
        instance.save(update_fields=['customer'])