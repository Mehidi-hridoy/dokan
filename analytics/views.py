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


# Signal to update customer stats when order is saved
from django.db.models.signals import post_save
from django.dispatch import receiver

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

def get_quick_stats():
    """Get quick overview statistics"""
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
    
    # Low stock products
    low_stock_products = Product.objects.filter(stock_quantity__lte=10).count()
    
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

def get_recent_activities():
    """Get recent activities for dashboard"""
    recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:5]
    recent_expenses = Expense.objects.select_related('category', 'created_by').order_by('-date')[:5]
    recent_damages = DamageReport.objects.select_related('product', 'reported_by').filter(resolved=False).order_by('-date_reported')[:5]
    
    activities = []
    
    # Add orders
    for order in recent_orders:
        activities.append({
            'type': 'order',
            'title': f'New Order #{order.order_number}',
            'description': f'{order.get_customer_display()} placed an order',
            'amount': order.total,
            'timestamp': order.created_at,
            'status': order.order_status,
            'icon': 'fas fa-shopping-cart',
            'color': 'blue',
        })
    
    # Add expenses
    for expense in recent_expenses:
        activities.append({
            'type': 'expense',
            'title': f'Expense: {expense.category.name}',
            'description': expense.description,
            'amount': -expense.amount,
            'timestamp': expense.created_at,
            'status': 'recorded',
            'icon': 'fas fa-receipt',
            'color': 'red',
        })
    
    # Add damages
    for damage in recent_damages:
        activities.append({
            'type': 'damage',
            'title': f'Damage Report: {damage.product.products_name}',
            'description': f'{damage.quantity} units damaged',
            'amount': -damage.cost_amount,
            'timestamp': damage.date_reported,
            'status': damage.damage_type,
            'icon': 'fas fa-exclamation-triangle',
            'color': 'orange',
        })
    
    # Sort by timestamp and return top 10
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    return activities[:10]

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

def calculate_percentage_change(current, previous):
    """Calculate percentage change between current and previous values"""
    if previous == 0:
        return Decimal('100.00') if current > 0 else Decimal('0.00')
    return ((current - previous) / abs(previous) * 100).quantize(Decimal('0.01'))

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