# analytics/views.py
from django.views.generic import TemplateView
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
import json
from datetime import timedelta
from orders.models import ORDER_STATUS_CHOICES
from orders.models import Order
from inventory.models import Inventory
from products.models import Product
from users.models import User  # Assuming Customer is User or extend
# analytics/views.py
from django.views.generic import ListView, DetailView
from django.db.models import Q, Sum
from django.shortcuts import render
from .models import Customer
from orders.models import Order  # For detail view orders



class BaseAnalyticsView(TemplateView):
    """Base for common data."""
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Common: Last 30 days filter
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        context['date_range'] = {'start': start_date, 'end': end_date}
        return context

class AnalyticsDashboard(BaseAnalyticsView):
    template_name = 'analytics/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orders = Order.objects.filter(order_status__in=['processed', 'delivered'])
        context['total_revenue'] = orders.aggregate(Sum('total'))['total__sum'] or 0
        context['total_orders'] = orders.count()
        context['low_stock_count'] = Inventory.objects.low_stock().count()
        context['out_of_stock_count'] = Inventory.objects.out_of_stock().count()
        context['active_customers'] = User.objects.filter(order__order_status='processed').distinct().count()

        # Revenue trend
        revenue_trend = orders.filter(created_at__date__gte=context['date_range']['start']) \
            .extra({'day': 'date(created_at)'}).values('day').annotate(revenue=Sum('total')).order_by('day')
        context['revenue_dates'] = json.dumps([item['day'].strftime('%Y-%m-%d') for item in revenue_trend], cls=DjangoJSONEncoder)
        context['revenue_values'] = json.dumps([float(item['revenue'] or 0) for item in revenue_trend], cls=DjangoJSONEncoder)

        # Top products (by order associations; placeholder)
        context['top_products'] = Product.objects.annotate(sales_count=Count('order')).order_by('-sales_count')[:5]

        # Recent orders
        context['recent_orders'] = Order.objects.order_by('-created_at')[:5]

        # Inventory pie
        context['in_stock_count'] = Inventory.objects.in_stock().count()
        return context

class SalesAnalyticsView(BaseAnalyticsView):
    template_name = 'analytics/sales.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start = self.request.GET.get('start_date', context['date_range']['start'])
        end = self.request.GET.get('end_date', context['date_range']['end'])
        orders = Order.objects.filter(created_at__date__range=[start, end], order_status__in=['processed', 'delivered'])

        context['total_sales'] = orders.count()
        context['avg_order_value'] = orders.aggregate(Avg('total'))['total__avg	j'] or 0
        context['top_products'] = Product.objects.annotate(sales_count=Count('order'), revenue=Sum('order__total')).order_by('-sales_count')[:10]

        # Sales trend (bar)
        sales_trend = orders.extra({'day': 'date(created_at)'}).values('day').annotate(sales=Count('id')).order_by('day')
        context['sales_dates'] = json.dumps([item['day'].strftime('%Y-%m-%d') for item in sales_trend], cls=DjangoJSONEncoder)
        context['sales_values'] = json.dumps([item['sales'] for item in sales_trend], cls=DjangoJSONEncoder)

        context['top_product'] = context['top_products'].first()
        return context

class OrdersAnalyticsView(BaseAnalyticsView):
    template_name = 'analytics/orders.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status = self.request.GET.get('status')
        orders = Order.objects.all()
        if status:
            orders = orders.filter(order_status=status)

        context['order_status_choices'] = Order.ORDER_STATUS
        context['pending_count'] = Order.objects.filter(order_status='pending').count()
        context['processed_count'] = Order.objects.filter(order_status='processed').count()
        context['delivered_count'] = Order.objects.filter(order_status='delivered').count()
        context['cancelled_count'] = Order.objects.filter(order_status='cancelled').count()

        # Status pie
        status_data = orders.values('order_status').annotate(count=Count('id'))
        context['status_labels'] = json.dumps([dict(Order.ORDER_STATUS).get(s['order_status'], s['order_status']) for s in status_data], cls=DjangoJSONEncoder)
        context['status_values'] = json.dumps([s['count'] for s in status_data], cls=DjangoJSONEncoder)

        context['recent_orders'] = orders.order_by('-created_at')[:10]
        return context

class InventoryAnalyticsView(BaseAnalyticsView):
    template_name = 'analytics/inventory.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        inv = Inventory.objects.select_related('product')
        context['total_items'] = inv.count()
        context['low_stock_count'] = inv.low_stock().count()
        context['out_of_stock_count'] = inv.out_of_stock().count()
        context['total_stock_value'] = sum(i.available_quantity * i.product.current_price for i in inv if i.product.current_price) or 0

        # Pie data
        context['stock_data'] = json.dumps({
            'in': inv.in_stock().count(),
            'low': context['low_stock_count'],
            'out': context['out_of_stock_count']
        }, cls=DjangoJSONEncoder)

        context['low_stock_items'] = inv.low_stock()[:10]
        return context

class ProductsAnalyticsView(BaseAnalyticsView):
    template_name = 'analytics/products.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        products = Product.objects.select_related('inventory').annotate(
            sales_count=Count('order'), revenue=Sum('order__total')
        ).order_by('-sales_count')
        context['products'] = products
        context['out_of_stock_products'] = products.filter(inventory__quantity=0)
        context['best_sellers'] = products[:5]

        # Bar for best sellers
        context['product_names'] = json.dumps([p.products_name for p in context['best_sellers']], cls=DjangoJSONEncoder)
        context['product_sales'] = json.dumps([p.sales_count for p in context['best_sellers']], cls=DjangoJSONEncoder)
        return context

class RevenueAnalyticsView(BaseAnalyticsView):
    template_name = 'analytics/revenue.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orders = Order.objects.filter(order_status__in=['processed', 'delivered'])
        context['total_revenue'] = orders.aggregate(Sum('total'))['total__sum'] or 0

        # Monthly
        monthly = orders.extra({'month': "strftime('%%Y-%%m', created_at)"}).values('month').annotate(revenue=Sum('total')).order_by('month')
        context['monthly_labels'] = json.dumps([m['month'] for m in monthly], cls=DjangoJSONEncoder)
        context['monthly_values'] = json.dumps([float(m['revenue'] or 0) for m in monthly], cls=DjangoJSONEncoder)

        # By payment
        payment_data = orders.values('payment_method').annotate(revenue=Sum('total'))
        context['payment_labels'] = json.dumps([dict(Order.PAYMENT_METHODS).get(p['payment_method'], p['payment_method']) for p in payment_data], cls=DjangoJSONEncoder)
        context['payment_values'] = json.dumps([float(p['revenue'] or 0) for p in payment_data], cls=DjangoJSONEncoder)

        # Daily trend
        daily = orders.filter(created_at__date__gte=context['date_range']['start']).extra({'day': 'date(created_at)'}).values('day').annotate(revenue=Sum('total')).order_by('day')
        context['daily_dates'] = json.dumps([d['day'].strftime('%Y-%m-%d') for d in daily], cls=DjangoJSONEncoder)
        context['daily_values'] = json.dumps([float(d['revenue'] or 0) for d in daily], cls=DjangoJSONEncoder)
        return context
    


class CustomerListView(ListView):
    model = Customer
    template_name = 'analytics/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 10  # 10 customers per page

    def get_queryset(self):
        queryset = Customer.objects.all().order_by('-total_spent')  # Default: high-value first
        
        # Search by name/email
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(email__icontains=search))
        
        # Sort
        sort = self.request.GET.get('sort', 'spent_desc')
        if sort == 'spent_desc':
            queryset = queryset.order_by('-total_spent')
        elif sort == 'spent_asc':
            queryset = queryset.order_by('total_spent')
        elif sort == 'orders_desc':
            queryset = queryset.order_by('-total_orders')
        elif sort == 'join_date':
            queryset = queryset.order_by('created_at')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any extra (e.g., total customers count)
        context['total_customers'] = Customer.objects.count()
        return context

class CustomerDetailView(DetailView):
    model = Customer
    template_name = 'analytics/customer_detail.html'
    context_object_name = 'customer'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch related orders (paginated)
        context['orders'] = self.object.orders.select_related('inventory').order_by('-created_at')[:20]  # Last 20 orders
        # Recalculate spent if needed (fallback to DB sum)
        context['lifetime_value'] = self.object.orders.aggregate(total=Sum('total'))['total'] or 0
        return context