from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Count, F, Q, DecimalField
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone

# Import models from other apps (assuming standard structure)
from inventory.models import Inventory, StockMovement
from products.models import Product 
from users.models import User # Assuming your 'customers' are your User model

# Note: You'll need to adjust the 'users.models' import if your Customer model 
# is separate or in a different location.

# ==============================================================================
# 1. Main Dashboard Views
# ==============================================================================

# In analytics/views.py

@login_required
def analytics_dashboard(request):
    """
    Renders the main analytics dashboard.
    """
    from inventory.models import Inventory
    
    low_stock_count = Inventory.objects.low_stock().count()
    out_of_stock_count = Inventory.objects.out_of_stock().count()
    total_products = Product.objects.filter(is_active=True).count()
    
    # --- FIX APPLIED HERE ---
    # Assume you are calculating a metric like 'stock difference from last week'
    # For demonstration, let's create a placeholder value:
    
    # Get the current total quantity available
    current_stock = Inventory.objects.aggregate(total=Sum('quantity'))['total'] or 0
    # Simulate a "target" or "previous" stock value
    target_stock = 100 
    
    stock_change = current_stock - target_stock
    # Calculate the absolute change and pass it
    absolute_stock_change = abs(stock_change) 
    
    # Also pass the raw change if you need to show 'up' or 'down'
    
    context = {
        'total_products': total_products,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'last_updated': timezone.now(),
        
        # New variables to replace the faulty template filter
        'stock_change': stock_change, 
        'absolute_stock_change': absolute_stock_change,
    }
    return render(request, 'analytics/dashboard.html', context)
# ==============================================================================
# 2. Customer Analytics Views (Using 'users.User' as Customer)
# ==============================================================================

@login_required
def customer_analytics(request):
    """
    Displays a list of customers and high-level customer metrics.
    Requires linking to an 'Order' model for true customer analytics (e.g., total spend).
    """
    # Filter users who are not staff/superuser to treat them as customers
    customers = User.objects.filter(is_active=True, is_staff=False).annotate(
        # Placeholder for future: total_orders=Count('orders'), total_spent=Sum('orders__total')
    ).order_by('-date_joined')[:50] # Show 50 latest customers
    
    context = {
        'total_customers': User.objects.filter(is_staff=False).count(),
        'customers': customers,
    }
    return render(request, 'analytics/customer_list.html', context)


@login_required
def customer_detail(request, customer_id):
    """
    Displays detailed analytics for a single customer.
    """
    customer = get_object_or_404(User, pk=customer_id, is_staff=False)
    
    context = {
        'customer': customer,
        # Placeholder for future: 'orders': customer.orders.all().order_by('-created_at')[:10],
    }
    return render(request, 'analytics/customer_detail.html', context)


@login_required
@require_http_methods(["POST"])
def toggle_customer_status(request, customer_id):
    """
    Toggles the is_active status of a customer (for soft-deleting/deactivating).
    """
    customer = get_object_or_404(User, pk=customer_id, is_staff=False)
    customer.is_active = not customer.is_active
    customer.save()
    
    # In a real application, you'd redirect or return a success message/JSON
    return JsonResponse({'status': 'success', 'is_active': customer.is_active})


@login_required
def customer_search_api(request):
    """
    API endpoint for searching customers (useful for auto-complete/AJAX search).
    """
    query = request.GET.get('q', '')
    if query:
        customers = User.objects.filter(
            Q(email__icontains=query) | 
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).filter(is_staff=False).values('id', 'email', 'first_name', 'last_name')[:10]
    else:
        customers = []
        
    return JsonResponse(list(customers), safe=False)

# ==============================================================================
# 3. Financial/Sales Analytics Views (Requires Order/Sale data)
# ==============================================================================

@login_required
def sales_analytics_detail(request):
    """
    Shows detailed sales metrics. 
    This is based on the assumption you have (or will have) an 'Order' model 
    that links to 'Product' and has price data.
    """
    # Placeholder: Calculate basic sales metrics based on StockMovement
    # This is a very rough proxy for sales
    sales_movements_today = StockMovement.objects.filter(
        movement_type='out', created_at__date=timezone.now().date()
    ).aggregate(
        total_quantity_out=Sum('quantity')
    )
    
    # Placeholder for future: Total revenue, top-selling products from OrderItem
    
    context = {
        'quantity_out_today': sales_movements_today.get('total_quantity_out') or 0,
        # 'total_revenue_ytd': 0.00, # Would come from Order model
    }
    return render(request, 'analytics/sales_detail.html', context)


@login_required
def financial_dashboard(request):
    """
    High-level financial overview.
    Requires data from Sales, Expenses, and Cost of Goods Sold (COGS).
    """
    # Calculate total COGS from sold products (using current cost_price as a proxy)
    # This calculation is highly complex and depends on the Order model.
    # For now, just show the most expensive products as a proxy for high-cost items.
    
    high_cost_products = Product.objects.filter(
        cost_price__isnull=False
    ).order_by('-cost_price')[:10]
    
    context = {
        # 'total_revenue': 0.00, # From Orders
        # 'total_expenses': 0.00, # From an Expense model
        # 'net_profit': 0.00,
        'high_cost_products': high_cost_products
    }
    return render(request, 'analytics/financial_dashboard.html', context)


@login_required
def expense_analytics_detail(request):
    """
    Displays detailed expense breakdown.
    Requires an 'Expense' model (not provided in the current structure).
    """
    # Placeholder: Just show the sum of 'damaged' stock value as a form of 'loss/expense'
    damaged_movements = StockMovement.objects.filter(movement_type='damged').aggregate(
        total_damaged_items=Sum('quantity')
    )
    
    context = {
        # 'total_operational_expense': 0.00, # From Expense model
        'total_damaged_items': damaged_movements.get('total_damaged_items') or 0,
    }
    return render(request, 'analytics/expense_detail.html', context)

# ==============================================================================
# 4. API Endpoints
# ==============================================================================

@login_required
def dashboard_data_api(request):
    """
    API endpoint to quickly fetch data for charts and widgets on the dashboard.
    """
    # Calculate real-time inventory stats
    inventory_stats = Inventory.objects.aggregate(
        total_items=Count('id'),
        low_stock=Count('id', filter=Q(quantity__lte=F('low_stock_threshold'), quantity__gt=0)),
        out_of_stock=Count('id', filter=Q(quantity=0)),
        available_qty_sum=Sum(F('quantity') - F('reserved_quantity')),
        reserved_qty_sum=Sum('reserved_quantity')
    )
    
    # Fetch recent stock movements for a widget
    recent_movements = StockMovement.objects.all().order_by('-created_at')[:5].values(
        'movement_type', 'quantity', 'created_at', 'inventory__product__products_name'
    )

    data = {
        'inventory_summary': {
            'total_products': inventory_stats['total_items'],
            'low_stock_count': inventory_stats['low_stock'],
            'out_of_stock_count': inventory_stats['out_of_stock'],
            'available_quantity': inventory_stats['available_qty_sum'],
            'reserved_quantity': inventory_stats['reserved_qty_sum'],
        },
        'recent_activity': list(recent_movements),
        # 'sales_over_time': [date, revenue, ...], # Requires DailyAnalytics or Order model
    }
    return JsonResponse(data)