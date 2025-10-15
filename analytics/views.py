from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Count, Q, Sum, F
from orders.models import Order, OrderItem
from products.models import Product
from django import forms
from django.core.exceptions import ValidationError
from .models import Customer, FinancialRecord, Expense, DamageReport
from django.shortcuts import get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from django.http import JsonResponse
from decimal import Decimal
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from .models import Customer

# Signal to update customer stats when order is saved
from django.db.models.signals import post_save
from django.dispatch import receiver

def get_quick_stats():
    """Get quick overview statistics"""
    from inventory.models import Inventory
    
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    # Today's stats
    today_orders = Order.objects.filter(created_at__date=today)
    today_sales = today_orders.filter(payment_status='paid').aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')
    
    # Yesterday's stats for comparison
    yesterday_orders = Order.objects.filter(created_at__date=yesterday)
    yesterday_sales = yesterday_orders.filter(payment_status='paid').aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')
    
    # Calculate changes
    sales_change = calculate_percentage_change(today_sales, yesterday_sales)
    orders_change = calculate_percentage_change(today_orders.count(), yesterday_orders.count())
    
    # Low stock products - using Inventory model
    low_stock_products = Inventory.objects.filter(
        quantity__lte=10,
        quantity__gt=0
    ).count()
    
    # Pending orders
    pending_orders = Order.objects.filter(order_status='pending').count()
    
    return {
        'today_sales': today_sales,
        'today_orders': today_orders.count(),
        'sales_change': sales_change,
        'orders_change': orders_change,
        'low_stock_products': low_stock_products,
        'pending_orders': pending_orders,
        'today_date': today,
    }

def get_customer_analytics(start_date, end_date):
    """Get comprehensive customer analytics"""
    
    # Base customer stats
    total_customers = Customer.objects.filter(
        first_order_date__date__lte=end_date
    ).count()
    
    new_customers = Customer.objects.filter(
        first_order_date__date__gte=start_date,
        first_order_date__date__lte=end_date
    ).count()
    
    # Customer segmentation
    customer_segments = Customer.objects.aggregate(
        new_customers=Count('id', filter=Q(total_orders=1)),
        regular_customers=Count('id', filter=Q(total_orders__gte=2, total_orders__lte=5)),
        vip_customers=Count('id', filter=Q(total_orders__gte=6)),
        fraudulent_customers=Count('id', filter=Q(is_fraudulent=True))
    )
    
    # Customer value metrics
    customer_value_stats = Customer.objects.aggregate(
        avg_order_value=Avg('total_spent', filter=Q(total_orders__gt=0)),
        avg_orders_per_customer=Avg('total_orders', filter=Q(total_orders__gt=0)),
        max_spent=Max('total_spent')
    )
    
    # Repeat customer rate
    repeat_customers = Customer.objects.filter(total_orders__gte=2).count()
    repeat_rate = (repeat_customers / total_customers * 100) if total_customers > 0 else 0
    
    # Customer acquisition trend
    acquisition_trend = []
    current_date = start_date
    while current_date <= end_date:
        daily_new = Customer.objects.filter(
            first_order_date__date=current_date
        ).count()
        acquisition_trend.append({
            'date': current_date,
            'new_customers': daily_new
        })
        current_date += timedelta(days=1)
    
    return {
        'total_customers': total_customers,
        'new_customers': new_customers,
        'segments': customer_segments,
        'value_metrics': customer_value_stats,
        'repeat_rate': repeat_rate,
        'repeat_customers': repeat_customers,
        'acquisition_trend': acquisition_trend,
    }

def get_financial_overview(start_date, end_date, days):
    """Get comprehensive financial overview"""
    
    # Sales revenue
    paid_orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        payment_status='paid'
    )
    
    total_revenue = paid_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')
    avg_daily_revenue = total_revenue / days if days > 0 else Decimal('0')
    
    # Expenses
    expenses = Expense.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Damages
    damages = DamageReport.objects.filter(
        date_reported__date__gte=start_date,
        date_reported__date__lte=end_date
    ).aggregate(total=Sum('cost_amount'))['total'] or Decimal('0')
    
    # Net profit
    total_expenses = expenses + damages
    net_profit = total_revenue - total_expenses
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else Decimal('0')
    
    # Comparison with previous period
    prev_start = start_date - timedelta(days=days)
    prev_end = start_date - timedelta(days=1)
    
    prev_revenue = Order.objects.filter(
        created_at__date__gte=prev_start,
        created_at__date__lte=prev_end,
        payment_status='paid'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    revenue_change = calculate_percentage_change(total_revenue, prev_revenue)
    
    # Daily revenue trend
    daily_revenue_trend = []
    current_date = start_date
    while current_date <= end_date:
        daily_rev = Order.objects.filter(
            created_at__date=current_date,
            payment_status='paid'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0')
        
        daily_revenue_trend.append({
            'date': current_date,
            'revenue': daily_rev
        })
        current_date += timedelta(days=1)
    
    return {
        'total_revenue': total_revenue,
        'avg_daily_revenue': avg_daily_revenue,
        'expenses': expenses,
        'damages': damages,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'profit_margin': profit_margin,
        'revenue_change': revenue_change,
        'previous_revenue': prev_revenue,
        'daily_revenue_trend': daily_revenue_trend,
    }

def get_sales_analytics(start_date, end_date):
    """Get detailed sales analytics"""
    
    # Order metrics
    orders_data = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).aggregate(
        total_orders=Count('id'),
        completed_orders=Count('id', filter=Q(order_status='confirmed')),
        pending_orders=Count('id', filter=Q(order_status='pending')),
        cancelled_orders=Count('id', filter=Q(order_status='rejected')),
        total_revenue=Sum('total', filter=Q(payment_status='paid')),
        avg_order_value=Avg('total', filter=Q(payment_status='paid'))
    )
    
    # Sales by status
    status_breakdown = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).values('order_status').annotate(
        count=Count('id'),
        revenue=Sum('total', filter=Q(payment_status='paid'))
    ).order_by('-revenue')
    
    # Daily sales trend
    daily_sales = []
    current_date = start_date
    while current_date <= end_date:
        daily_revenue = Order.objects.filter(
            created_at__date=current_date,
            payment_status='paid'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0')
        
        daily_orders = Order.objects.filter(
            created_at__date=current_date
        ).count()
        
        daily_sales.append({
            'date': current_date,
            'revenue': daily_revenue,
            'orders': daily_orders
        })
        
        current_date += timedelta(days=1)
    
    # Payment method breakdown
    payment_methods = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        payment_status='paid'
    ).exclude(payment_method__isnull=True).values('payment_method').annotate(
        count=Count('id'),
        total_revenue=Sum('total')
    ).order_by('-total_revenue')
    
    return {
        'orders': orders_data,
        'status_breakdown': list(status_breakdown),
        'daily_sales': daily_sales,
        'payment_methods': list(payment_methods),
    }

def get_product_analytics(start_date, end_date):
    """Get product performance analytics"""
    from inventory.models import Inventory
    
    # Top selling products
    top_products = OrderItem.objects.filter(
        order__created_at__date__gte=start_date,
        order__created_at__date__lte=end_date,
        order__payment_status='paid'
    ).values(
        'product__id',
        'product__products_name',
        'product__product_code',
        'product__base_price',
        'product__sale_price',
    ).annotate(
        units_sold=Sum('quantity'),
        total_revenue=Sum(F('unit_price') * F('quantity')),
        order_count=Count('order', distinct=True)
    ).order_by('-total_revenue')[:10]
    
    # Products by category
    category_performance = OrderItem.objects.filter(
        order__created_at__date__gte=start_date,
        order__created_at__date__lte=end_date,
        order__payment_status='paid'
    ).values(
        'product__category__name'
    ).annotate(
        units_sold=Sum('quantity'),
        total_revenue=Sum(F('unit_price') * F('quantity'))
    ).order_by('-total_revenue')
    
    # Low stock alerts - using Inventory model
    low_stock_products = Inventory.objects.filter(
        quantity__lte=10,
        quantity__gt=0
    ).count()
    
    # Out of stock products
    out_of_stock_products = Inventory.objects.filter(
        quantity=0
    ).count()
    
    # Best performing categories
    best_categories = list(category_performance[:5])
    
    return {
        'top_products': list(top_products),
        'category_performance': list(category_performance),
        'best_categories': best_categories,
        'low_stock_alerts': low_stock_products,
        'out_of_stock': out_of_stock_products,
    }

def get_operations_analytics():
    """Get operations and inventory analytics"""
    from inventory.models import Inventory, StockAlert
    
    # Inventory summary - using Inventory model
    inventory_stats = Inventory.objects.aggregate(
        total_products=Count('id'),
        in_stock_products=Count('id', filter=Q(quantity__gt=0)),
        total_stock_value=Sum(
            Case(
                When(product__sale_price__isnull=False, then=F('product__sale_price') * F('quantity')),
                default=F('product__base_price') * F('quantity'),
                output_field=models.DecimalField()
            )
        ),
        avg_stock_quantity=Avg('quantity')
    )
    
    # Recent damages
    recent_damages = DamageReport.objects.filter(resolved=False).aggregate(
        total_cost=Sum('cost_amount'),
        total_units=Sum('quantity')
    )
    
    # Pending orders requiring action
    pending_actions = {
        'pending_orders': Order.objects.filter(order_status='pending').count(),
        'unresolved_damages': DamageReport.objects.filter(resolved=False).count(),
        'low_stock_items': Inventory.objects.filter(
            quantity__lte=10,
            quantity__gt=0
        ).count(),
    }
    
    # Shipping and delivery stats
    shipping_stats = Order.objects.filter(
        courier_status__isnull=False
    ).values('courier_status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Stock alerts
    active_alerts = StockAlert.objects.filter(status='active').count()
    
    return {
        'inventory': inventory_stats,
        'damages': recent_damages,
        'pending_actions': pending_actions,
        'shipping_stats': list(shipping_stats),
        'active_alerts': active_alerts,
    }

def get_recent_activities():
    """Get recent business activities"""
    from inventory.models import StockMovement
    
    recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:5]
    recent_expenses = Expense.objects.select_related('category', 'created_by').order_by('-date')[:5]
    recent_damages = DamageReport.objects.select_related('product', 'reported_by').filter(resolved=False).order_by('-date_reported')[:5]
    recent_customers = Customer.objects.filter(
        first_order_date__isnull=False
    ).order_by('-first_order_date')[:3]
    
    # Recent stock movements
    recent_stock_movements = StockMovement.objects.select_related('inventory__product').order_by('-created_at')[:3]
    
    activities = []
    
    # Add orders
    for order in recent_orders:
        activities.append({
            'type': 'order',
            'title': f'New Order #{order.order_number}',
            'description': f'{order.get_customer_display()} - ৳{order.total}',
            'amount': order.total,
            'timestamp': order.created_at,
            'status': order.order_status,
            'icon': 'fas fa-shopping-cart',
            'color': 'success' if order.order_status == 'confirmed' else 'warning',
        })
    
    # Add expenses
    for expense in recent_expenses:
        activities.append({
            'type': 'expense',
            'title': f'Expense: {expense.category.name}',
            'description': expense.description[:50] + '...' if len(expense.description) > 50 else expense.description,
            'amount': -expense.amount,
            'timestamp': expense.created_at,
            'status': 'recorded',
            'icon': 'fas fa-receipt',
            'color': 'danger',
        })
    
    # Add damages
    for damage in recent_damages:
        activities.append({
            'type': 'damage',
            'title': f'Damage: {damage.product.products_name}',
            'description': f'{damage.quantity} units - ৳{damage.cost_amount}',
            'amount': -damage.cost_amount,
            'timestamp': damage.date_reported,
            'status': damage.damage_type,
            'icon': 'fas fa-exclamation-triangle',
            'color': 'warning',
        })
    
    # Add new customers
    for customer in recent_customers:
        activities.append({
            'type': 'customer',
            'title': f'New Customer: {customer.name}',
            'description': f'Joined with {customer.total_orders} orders',
            'amount': customer.total_spent,
            'timestamp': customer.first_order_date or customer.created_at,
            'status': customer.customer_type,
            'icon': 'fas fa-user-plus',
            'color': 'info',
        })
    
    # Add stock movements
    for movement in recent_stock_movements:
        activities.append({
            'type': 'stock',
            'title': f'Stock {movement.get_movement_type_display()}',
            'description': f'{movement.inventory.product.products_name} - {movement.quantity} units',
            'amount': movement.quantity,
            'timestamp': movement.created_at,
            'status': movement.movement_type,
            'icon': 'fas fa-boxes',
            'color': 'primary' if movement.movement_type == 'in' else 'secondary',
        })
    
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    return activities[:10]

def get_business_kpis(start_date, end_date, days):
    """Calculate key performance indicators"""
    from inventory.models import Inventory
    
    # Sales KPIs
    paid_orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        payment_status='paid'
    )
    
    total_revenue = paid_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')
    total_orders = paid_orders.count()
    
    # Customer KPIs
    new_customers = Customer.objects.filter(
        first_order_date__date__gte=start_date,
        first_order_date__date__lte=end_date
    ).count()
    
    # Product KPIs
    total_products_sold = OrderItem.objects.filter(
        order__created_at__date__gte=start_date,
        order__created_at__date__lte=end_date,
        order__payment_status='paid'
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Calculate rates and averages
    avg_order_value = total_revenue / total_orders if total_orders > 0 else Decimal('0')
    conversion_rate = (paid_orders.filter(order_status='confirmed').count() / total_orders * 100) if total_orders > 0 else 0
    daily_sales = total_revenue / days if days > 0 else Decimal('0')
    
    # Customer retention rate (simplified)
    returning_customers = Customer.objects.filter(
        total_orders__gte=2,
        last_order_date__date__gte=start_date
    ).count()
    retention_rate = (returning_customers / new_customers * 100) if new_customers > 0 else 0
    
    # Inventory turnover (simplified) - using Inventory model
    total_inventory_value = Inventory.objects.aggregate(
        total=Sum(
            Case(
                When(product__sale_price__isnull=False, then=F('product__sale_price') * F('quantity')),
                default=F('product__base_price') * F('quantity'),
                output_field=models.DecimalField()
            )
        )
    )['total'] or Decimal('0')
    inventory_turnover = (total_revenue / total_inventory_value) if total_inventory_value > 0 else Decimal('0')
    
    # Stock health metrics
    stock_health = Inventory.objects.aggregate(
        out_of_stock=Count('id', filter=Q(quantity=0)),
        low_stock=Count('id', filter=Q(quantity__lte=10, quantity__gt=0)),
        healthy_stock=Count('id', filter=Q(quantity__gt=10))
    )
    
    return {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'new_customers': new_customers,
        'products_sold': total_products_sold,
        'avg_order_value': avg_order_value,
        'conversion_rate': conversion_rate,
        'daily_sales': daily_sales,
        'retention_rate': retention_rate,
        'inventory_turnover': inventory_turnover,
        'returning_customers': returning_customers,
        'stock_health': stock_health,
    }


def calculate_percentage_change(current, previous):
    """Calculate percentage change between current and previous values"""
    current = Decimal(current)
    previous = Decimal(previous)

    if previous == 0:
        return Decimal('100.00') if current > 0 else Decimal('0.00')

    change = ((current - previous) / abs(previous) * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return change


class DateFilterForm(forms.Form):
    period = forms.ChoiceField(
        choices=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('last_7_days', 'Last 7 Days'),
            ('custom', 'Custom Range'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        period = cleaned_data.get('period')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if period == 'custom' and not (start_date and end_date):
            raise ValidationError("Please provide both start and end dates for custom range.")
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date.")
        return cleaned_data

def is_staff_or_admin(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_staff_or_admin)
def analytics_dashboard(request):
    """Main analytics dashboard for staff/admin users"""
    
    # Time periods
    today = timezone.now()
    
    # Customer Statistics
    customer_stats = Customer.objects.get_customer_stats()
    
    # Financial Overview
    financial_overview = Customer.objects.get_financial_overview(30)
    
    # Sales Analytics
    sales_analytics = Customer.objects.get_sales_analytics(30)
    
    # Expense Analytics
    expense_analytics = Customer.objects.get_expense_analytics(30)
    
    # Quick Stats
    quick_stats = get_quick_stats()
    
    # Recent Activities
    recent_activities = get_recent_activities()
    
    # Top Products
    top_products = get_top_products(10)
    
    context = {
        'customer_stats': customer_stats,
        'financial_overview': financial_overview,
        'sales_analytics': sales_analytics,
        'expense_analytics': expense_analytics,
        'quick_stats': quick_stats,
        'recent_activities': recent_activities,
        'top_products': top_products,
        'today': today.date(),
    }
    
    return render(request, 'analytics/dashboard.html', context)

@login_required
@user_passes_test(is_staff_or_admin)
def dashboard_data_api(request):
    """API endpoint for dashboard data (for AJAX updates)"""
    period_days = int(request.GET.get('period', 30))
    
    data = {
        'customer_stats': Customer.objects.get_customer_stats(),
        'financial_overview': Customer.objects.get_financial_overview(period_days),
        'sales_analytics': Customer.objects.get_sales_analytics(period_days),
        'expense_analytics': Customer.objects.get_expense_analytics(period_days),
        'quick_stats': get_quick_stats(),
        'timestamp': timezone.now().isoformat(),
    }
    
    return JsonResponse(data)


def get_top_products(limit=10):
    """Get top performing products"""
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    top_products = OrderItem.objects.filter(
        order__created_at__gte=thirty_days_ago,
        order__payment_status='paid'
    ).values(
        'product__id',
        'product__products_name',
        'product__product_code',
        'product__current_price',
        'product__stock_quantity',
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum(F('unit_price') * F('quantity')),
        order_count=Count('order', distinct=True)
    ).order_by('-total_revenue')[:limit]
    
    return list(top_products)


@login_required
@user_passes_test(is_staff_or_admin)
def customer_analytics(request):
    """Detailed customer analytics view"""
    customer_stats = Customer.objects.get_customer_stats()
    
    # Handle search
    search_query = request.GET.get('search', '')
    customers = Customer.objects.all().order_by('-created_at')
    
    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    # Filter by customer type
    customer_type = request.GET.get('type', '')
    if customer_type:
        customers = customers.filter(customer_type=customer_type)
    
    # Pagination
    paginator = Paginator(customers, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'customer_stats': customer_stats,
        'page_obj': page_obj,
        'search_query': search_query,
        'customer_type_filter': customer_type,
        'total_customers': customers.count(),
    }
    
    return render(request, 'analytics/customer_analytics.html', context)

@login_required
@user_passes_test(is_staff_or_admin)
def financial_analytics_view(request):
    """Detailed financial analytics view"""
    financial_overview = Customer.objects.get_financial_overview(30)
    expense_analytics = Customer.objects.get_expense_analytics(30)
    
    context = {
        'financial_overview': financial_overview,
        'expense_analytics': expense_analytics,
    }
    
    return render(request, 'analytics/financial_analytics.html', context)

@login_required
def customer_detail(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    
    # Get orders for this customer
    orders = Order.objects.filter(customer=customer).order_by('-created_at')
    
    # Order statistics for this customer
    order_stats = {
        'total_orders': orders.count(),
        'confirmed_orders': orders.filter(order_status='confirmed').count(),
        'pending_orders': orders.filter(order_status='pending').count(),
        'rejected_orders': orders.filter(order_status='rejected').count(),
        'total_spent': orders.filter(order_status='confirmed').aggregate(
            total=Sum('total')
        )['total'] or 0,
    }
    
    context = {
        'customer': customer,
        'orders': orders,
        'order_stats': order_stats,
    }
    
    return render(request, 'analytics/customer_detail.html', context)

@login_required
def toggle_customer_status(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'block':
            customer.is_fraudulent = True
            customer.customer_type = 'fraud'
            customer.save()
            messages.warning(request, f'{customer.name} has been marked as fraudulent.')
        elif action == 'unblock':
            customer.is_fraudulent = False
            customer.update_customer_stats()
            messages.success(request, f'{customer.name} has been unblocked.')
    
    return redirect('analytics:customer_detail', customer_id=customer_id)

@receiver(post_save, sender=Order)
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

@login_required
def customer_search_api(request):
    query = request.GET.get('q', '')
    
    if query:
        customers = Customer.objects.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query)
        )[:10]
        
        results = []
        for customer in customers:
            results.append({
                'id': customer.id,
                'name': customer.name,
                'email': customer.email,
                'phone': customer.phone,
                'type': customer.get_customer_type_display(),
                'total_orders': customer.total_orders,
                'total_spent': float(customer.total_spent),
            })
        
        return JsonResponse({'results': results})
    
    return JsonResponse({'results': []})

@login_required
@user_passes_test(is_staff_or_admin)
def financial_dashboard(request):
    """Comprehensive financial dashboard"""
    period_days = int(request.GET.get('period', 30))
    
    financial_overview = Customer.objects.get_financial_overview(period_days)
    sales_analytics = Customer.objects.get_sales_analytics(period_days)
    expense_analytics = Customer.objects.get_expense_analytics(period_days)
    
    recent_transactions = FinancialRecord.objects.all().order_by('-date')[:10]
    recent_damages = DamageReport.objects.filter(resolved=False).order_by('-date_reported')[:5]
    top_expenses = Expense.objects.all().order_by('-date')[:5]
    
    context = {
        'financial_overview': financial_overview,
        'sales_analytics': sales_analytics,
        'expense_analytics': expense_analytics,
        'recent_transactions': recent_transactions,
        'recent_damages': recent_damages,
        'top_expenses': top_expenses,
        'period_days': period_days,
        'period_options': [7, 30, 90, 365],
    }
    
    return render(request, 'analytics/financial_dashboard.html', context)

@login_required
@user_passes_test(is_staff_or_admin)
def sales_analytics_detail(request):
    """Detailed sales analytics view"""
    period_days = int(request.GET.get('period', 30))
    
    sales_data = Customer.objects.get_sales_analytics(period_days)
    
    context = {
        'sales_data': sales_data,
        'period_days': period_days,
        'period_options': [7, 30, 90, 365],
    }
    
    return render(request, 'analytics/sales_analytics.html', context)

@login_required
@user_passes_test(is_staff_or_admin)
def expense_analytics_detail(request):
    """Detailed expense analytics view"""
    period_days = int(request.GET.get('period', 30))
    
    expense_data = Customer.objects.get_expense_analytics(period_days)
    
    context = {
        'expense_data': expense_data,
        'period_days': period_days,
        'period_options': [7, 30, 90, 365],
    }
    
    return render(request, 'analytics/expense_analytics.html', context)