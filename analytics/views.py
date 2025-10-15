# analytics/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Sum, F, Q, Min, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

# Import Models from other apps (adjust imports based on your project structure)
from .models import Customer, ExpenseCategory, Expense, DamageReport, FinancialRecord
from orders.models import Order, OrderItem
from inventory.models import Inventory, StockMovement, StockAlert
from products.models import Product

# --- Utility Functions ---

def _get_period_dates(period_days=30):
    """Calculates start and end dates for the current reporting period."""
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)
    return start_date, end_date

# --- Dashboard & Financial Views ---

@login_required
def analytics_dashboard(request, period_days=30):
    """
    Main dashboard displaying a comprehensive overview (Customer, Financial, Sales).
    Uses the CustomerManager methods for aggregated data.
    """
    try:
        period_days = int(request.GET.get('period', period_days))
    except ValueError:
        period_days = 30 # Default to 30 days if invalid

    # Retrieve all aggregated data using CustomerManager methods
    customer_stats = Customer.objects.get_customer_stats()
    financial_overview = Customer.objects.get_financial_overview(period_days=period_days)
    sales_analytics = Customer.objects.get_sales_analytics(period_days=period_days)
    expense_analytics = Customer.objects.get_expense_analytics(period_days=period_days)
    
    # Inventory Summary
    total_products = Product.objects.filter(is_active=True).count()
    low_stock_count = Product.objects.low_stock().count()
    out_of_stock_count = Product.objects.out_of_stock().count()

    context = {
        'period_days': period_days,
        'customer_stats': customer_stats,
        'financial_overview': financial_overview,
        'sales_analytics': sales_analytics,
        'expense_analytics': expense_analytics,
        'inventory_summary': {
            'total_products': total_products,
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
        }
    }

    return render(request, 'analytics/analytics_dashboard.html', context)


@login_required
def sales_analytics_detail(request):
    """Detailed view for Sales Analytics."""
    period_days = int(request.GET.get('period', 30))
    sales_analytics = Customer.objects.get_sales_analytics(period_days=period_days)
    
    context = {
        'period_days': period_days,
        'sales_analytics': sales_analytics,
        'top_products': sales_analytics['top_products'] # Pass products directly for easy template iteration
    }
    return render(request, 'analytics/sales_analytics_detail.html', context)


@login_required
def expense_analytics_detail(request):
    """Detailed view for Expense Analytics."""
    period_days = int(request.GET.get('period', 30))
    expense_analytics = Customer.objects.get_expense_analytics(period_days=period_days)

    context = {
        'period_days': period_days,
        'expense_analytics': expense_analytics,
        'categories': expense_analytics['expenses_by_category'],
        'damage_analytics': expense_analytics['damage_analytics']
    }
    return render(request, 'analytics/expense_analytics_detail.html', context)


@login_required
def financial_dashboard(request):
    """Detailed view for Financial Overview (similar to dashboard but focused on finance)."""
    period_days = int(request.GET.get('period', 30))
    financial_overview = Customer.objects.get_financial_overview(period_days=period_days)

    context = {
        'period_days': period_days,
        'financial_overview': financial_overview,
    }
    return render(request, 'analytics/financial_dashboard.html', context)


@login_required
def financial_analytics(request):
    """
    View to display a detailed breakdown of FinancialRecords.
    This replaces the 'financial/' URL path.
    """
    record_type = request.GET.get('type')
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    records = FinancialRecord.objects.all()

    if record_type:
        records = records.filter(record_type=record_type)
    if start_date:
        records = records.filter(date__gte=start_date)
    if end_date:
        # Add one day to include the end date fully
        try:
            end_datetime = timezone.datetime.strptime(end_date, '%Y-%m-%d').date() + timedelta(days=1)
            records = records.filter(date__lt=end_datetime)
        except ValueError:
            pass # Ignore invalid date format

    total_amount = records.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    paginator = Paginator(records, 50) # Show 50 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'record_types': FinancialRecord.RECORD_TYPES,
        'total_amount': total_amount,
        'selected_type': record_type,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'analytics/financial_record_list.html', context)


# --- API Endpoint for Charts/Data ---

@login_required
def dashboard_data_api(request):
    """API endpoint to fetch data required for dashboard charts via AJAX."""
    period_days = int(request.GET.get('period', 30))
    
    sales_analytics = Customer.objects.get_sales_analytics(period_days=period_days)
    expense_analytics = Customer.objects.get_expense_analytics(period_days=period_days)
    
    # Prepare Daily Sales Data
    daily_sales_data = [{
        'date': item['date'].strftime('%Y-%m-%d'), 
        'revenue': item['daily_revenue'], 
        'orders': item['order_count']
    } for item in sales_analytics['daily_sales']]
    
    # Prepare Monthly Expenses Data
    monthly_expense_data = [{
        'month': item['month'], 
        'total': item['monthly_total']
    } for item in expense_analytics['monthly_expenses']]

    # Prepare Expense by Category Data
    expense_category_data = [{
        'label': item['category__name'], 
        'total': item['total'],
        'color': item['category__color']
    } for item in expense_analytics['expenses_by_category']]

    return JsonResponse({
        'daily_sales': daily_sales_data,
        'monthly_expenses': monthly_expense_data,
        'expense_by_category': expense_category_data,
    })

# --- Customer Management Views ---

@login_required
def customer_list(request):
    """List all customers with filtering and search."""
    customers = Customer.objects.all().prefetch_related('user')
    
    search_query = request.GET.get('q')
    customer_type = request.GET.get('type')
    
    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    if customer_type:
        customers = customers.filter(customer_type=customer_type)

    paginator = Paginator(customers, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_type': customer_type,
        'customer_types': Customer.CUSTOMER_TYPES,
    }
    return render(request, 'analytics/customer_list.html', context)


@login_required
def customer_detail(request, customer_id):
    """Detailed view for a specific customer."""
    customer = get_object_or_404(Customer, id=customer_id)
    
    # Fetch customer's orders
    orders = customer.orders_name.all().order_by('-created_at')[:10] # Last 10 orders

    # Get customer's total spent (redundant with model field but good for verification)
    total_spent_agg = Order.objects.filter(customer=customer, payment_status='paid').aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')

    context = {
        'customer': customer,
        'orders': orders,
        'total_spent_agg': total_spent_agg,
    }
    return render(request, 'analytics/customer_detail.html', context)


@login_required
def toggle_customer_status(request, customer_id):
    """Toggle the is_fraudulent status for a customer."""
    customer = get_object_or_404(Customer, id=customer_id)
    
    if request.method == 'POST':
        customer.is_fraudulent = not customer.is_fraudulent
        customer.save(update_fields=['is_fraudulent'])
        return redirect('analytics:customer_detail', customer_id=customer.id)
        
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)


@login_required
def customer_search_api(request):
    """API endpoint for live customer search."""
    query = request.GET.get('q', '')
    if query:
        customers = Customer.objects.filter(
            Q(name__icontains=query) | 
            Q(email__icontains=query) | 
            Q(phone__icontains=query)
        ).values('id', 'name', 'email', 'phone')[:10]
        
        return JsonResponse(list(customers), safe=False)
    return JsonResponse([], safe=False)