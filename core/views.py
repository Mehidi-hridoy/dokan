from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta
from .models import *

def home(request):
    return render(request, 'core/home.html')

def is_admin_user(user):
    return user.is_authenticated and (user.is_staff or user.user_type in ['admin', 'staff'])

@login_required
@user_passes_test(is_admin_user)
def admin_dashboard(request):
    # Calculate date ranges
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Order statistics
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()
    completed_orders = Order.objects.filter(status='delivered').count()
    
    # Revenue statistics
    total_revenue = Order.objects.filter(payment_status='paid').aggregate(
        total=Sum('total')
    )['total'] or 0
    
    weekly_revenue = Order.objects.filter(
        created_at__gte=week_ago,
        payment_status='paid'
    ).aggregate(total=Sum('total'))['total'] or 0
    
    # Customer statistics
    total_customers = User.objects.filter(user_type='customer').count()
    new_customers_week = User.objects.filter(
        date_joined__gte=week_ago,
        user_type='customer'
    ).count()
    
    # Product statistics
    total_products = Product.objects.count()
    low_stock_products = Inventory.objects.filter(
        quantity__lte=models.F('low_stock_threshold')
    ).count()
    out_of_stock_products = Inventory.objects.filter(quantity=0).count()
    
    # Recent orders
    recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:10]
    
    # Top selling products
    top_products = Product.objects.annotate(
        total_sold=Sum('orderitem__quantity')
    ).order_by('-total_sold')[:5]
    
    # Sales chart data (last 7 days)
    sales_data = []
    for i in range(7):
        date = today - timedelta(days=6-i)
        daily_sales = Order.objects.filter(
            created_at__date=date,
            payment_status='paid'
        ).aggregate(total=Sum('total'))['total'] or 0
        sales_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'sales': float(daily_sales)
        })
    
    context = {
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'total_revenue': total_revenue,
        'weekly_revenue': weekly_revenue,
        'total_customers': total_customers,
        'new_customers_week': new_customers_week,
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'sales_data': sales_data,
    }
    
    return render(request, 'admin/dashboard.html', context)

@login_required
@user_passes_test(is_admin_user)
def order_management(request):
    orders = Order.objects.select_related('customer').prefetch_related('items').all()
    
    # Filtering
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    payment_status_filter = request.GET.get('payment_status')
    if payment_status_filter:
        orders = orders.filter(payment_status=payment_status_filter)
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)
    
    context = {
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
        'payment_status_choices': Order.PAYMENT_STATUS_CHOICES,
    }
    return render(request, 'admin/order_management.html', context)

@login_required
@user_passes_test(is_admin_user)
def incomplete_orders(request):
    incomplete_orders = Order.objects.filter(
        Q(status='pending') | Q(status='confirmed') | Q(payment_status='pending')
    ).select_related('customer').prefetch_related('items')
    
    context = {
        'incomplete_orders': incomplete_orders,
    }
    return render(request, 'admin/incomplete_orders.html', context)

@login_required
@user_passes_test(is_admin_user)
def pos_management(request):
    products = Product.objects.filter(status='published').select_related('inventory')
    categories = Category.objects.filter(is_active=True)
    
    context = {
        'products': products,
        'categories': categories,
    }
    return render(request, 'admin/pos_management.html', context)

@login_required
@user_passes_test(is_admin_user)
def customer_info(request):
    customers = User.objects.filter(user_type='customer').annotate(
        order_count=Count('orders'),
        total_spent=Sum('orders__total')
    )
    
    context = {
        'customers': customers,
    }
    return render(request, 'admin/customer_info.html', context)

@login_required
@user_passes_test(is_admin_user)
def analytics_dashboard(request):
    # Sales analytics
    monthly_sales = Order.objects.filter(
        payment_status='paid',
        created_at__gte=timezone.now() - timedelta(days=365)
    ).extra({
        'month': "strftime('%%Y-%%m', created_at)"
    }).values('month').annotate(
        total_sales=Sum('total'),
        order_count=Count('id')
    ).order_by('month')
    
    # Customer analytics
    customer_acquisition = User.objects.filter(
        user_type='customer',
        date_joined__gte=timezone.now() - timedelta(days=365)
    ).extra({
        'month': "strftime('%%Y-%%m', date_joined)"
    }).values('month').annotate(
        new_customers=Count('id')
    ).order_by('month')
    
    # Product performance
    top_performing_products = Product.objects.annotate(
        total_sold=Sum('orderitem__quantity'),
        total_revenue=Sum('orderitem__total_price')
    ).order_by('-total_revenue')[:10]
    
    context = {
        'monthly_sales': list(monthly_sales),
        'customer_acquisition': list(customer_acquisition),
        'top_performing_products': top_performing_products,
    }
    return render(request, 'admin/analytics.html', context)

@login_required
@user_passes_test(is_admin_user)
def report_generator(request):
    report_type = request.GET.get('type', 'sales')
    
    if report_type == 'sales':
        data = Order.objects.filter(payment_status='paid')
    elif report_type == 'products':
        data = Product.objects.all()
    elif report_type == 'customers':
        data = User.objects.filter(user_type='customer')
    elif report_type == 'inventory':
        data = Inventory.objects.all()
    
    context = {
        'report_type': report_type,
        'data': data,
    }
    return render(request, 'admin/reports.html', context)

@login_required
@user_passes_test(is_admin_user)
def api_settings(request):
    api_keys = APIKey.objects.all()
    
    context = {
        'api_keys': api_keys,
    }
    return render(request, 'admin/api_settings.html', context)

@login_required
@user_passes_test(is_admin_user)
def access_management(request):
    users = User.objects.all()
    access_logs = AccessLog.objects.select_related('user').order_by('-created_at')[:100]
    
    context = {
        'users': users,
        'access_logs': access_logs,
    }
    return render(request, 'admin/access_management.html', context)