# analytics/views.py
from django.views.generic import TemplateView, ListView, DetailView
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import TruncDay, TruncMonth
from django.contrib.auth.models import User
from orders.models import Order, OrderItem
from products.models import Product
from datetime import timedelta
from django.utils import timezone

class AnalyticsDashboard(TemplateView):
    template_name = 'analytics/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)

        # Overall stats
        context['total_revenue'] = Order.objects.filter(status='completed').aggregate(total=Sum('total'))['total'] or 0
        context['total_orders'] = Order.objects.count()
        context['average_order_value'] = Order.objects.filter(status='completed').aggregate(avg=Avg('total'))['avg'] or 0
        context['total_customers'] = User.objects.count()

        # Order statuses
        context['completed_orders'] = Order.objects.filter(status='completed').count()
        context['pending_orders'] = Order.objects.filter(status='pending').count()
        context['processing_orders'] = Order.objects.filter(status='processing').count()
        context['canceled_orders'] = Order.objects.filter(status='canceled').count()
        context['on_delivery_orders'] = Order.objects.filter(status='on_delivery').count()  # Assuming 'on_delivery' status exists

        # Inventory stats
        context['total_stock'] = Product.objects.aggregate(total=Sum('available_quantity'))['total'] or 0
        context['in_stock_items'] = Product.objects.filter(is_in_stock=True).count()
        context['low_stock_items'] = Product.objects.filter(available_quantity__lt=10, available_quantity__gt=0).count()  # Example threshold
        context['out_of_stock_items'] = Product.objects.filter(available_quantity=0).count()

        # Recent activity (last 30 days)
        context['new_customers_last_30'] = User.objects.filter(date_joined__gte=last_30_days).count()
        context['revenue_last_30'] = Order.objects.filter(status='completed', created_at__gte=last_30_days).aggregate(total=Sum('total'))['total'] or 0

        # Charts data (e.g., daily sales for last 30 days - JSON for Chart.js)
        daily_sales = Order.objects.filter(status='completed', created_at__gte=last_30_days).annotate(
            day=TruncDay('created_at')
        ).values('day').annotate(total=Sum('total')).order_by('day')
        context['daily_sales_data'] = {
            'labels': [item['day'].strftime('%Y-%m-%d') for item in daily_sales],
            'data': [float(item['total']) for item in daily_sales],
        }

        return context

class SalesAnalyticsView(TemplateView):
    template_name = 'analytics/sales.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        last_year = timezone.now().date() - timedelta(days=365)

        # Sales metrics
        context['total_revenue'] = Order.objects.filter(status='completed').aggregate(total=Sum('total'))['total'] or 0
        context['monthly_revenue'] = Order.objects.filter(status='completed', created_at__gte=last_year).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(total=Sum('total')).order_by('month')

        # Top customers by spend
        context['top_customers'] = User.objects.annotate(
            total_spent=Sum('order__total', filter=Q(order__status='completed'))
        ).order_by('-total_spent')[:10]

        # Charts data
        context['monthly_revenue_data'] = {
            'labels': [item['month'].strftime('%b %Y') for item in context['monthly_revenue']],
            'data': [float(item['total']) for item in context['monthly_revenue']],
        }

        return context

class OrdersAnalyticsView(TemplateView):
    template_name = 'analytics/orders.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Order statuses breakdown
        context['order_statuses'] = Order.objects.values('status').annotate(count=Count('id')).order_by('-count')

        # Orders over time
        last_30_days = timezone.now().date() - timedelta(days=30)
        context['daily_orders'] = Order.objects.filter(created_at__gte=last_30_days).annotate(
            day=TruncDay('created_at')
        ).values('day').annotate(count=Count('id')).order_by('day')

        # Pending, processing, on delivery, confirmed, canceled
        context['pending_orders'] = Order.objects.filter(status='pending').count()
        context['processing_orders'] = Order.objects.filter(status='processing').count()
        context['on_delivery_orders'] = Order.objects.filter(status='on_delivery').count()
        context['confirmed_orders'] = Order.objects.filter(status='confirmed').count()
        context['canceled_orders'] = Order.objects.filter(status='canceled').count()

        # Charts data
        context['daily_orders_data'] = {
            'labels': [item['day'].strftime('%Y-%m-%d') for item in context['daily_orders']],
            'data': [item['count'] for item in context['daily_orders']],
        }

        return context

class InventoryAnalyticsView(TemplateView):
    template_name = 'analytics/inventory.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Inventory metrics
        context['total_products'] = Product.objects.count()
        context['total_stock'] = Product.objects.aggregate(total=Sum('available_quantity'))['total'] or 0
        context['low_stock'] = Product.objects.filter(available_quantity__lt=10, available_quantity__gt=0).count()
        context['out_of_stock'] = Product.objects.filter(available_quantity=0).count()

        # Top low stock products
        context['low_stock_products'] = Product.objects.filter(available_quantity__lt=10).order_by('available_quantity')[:10]

        # Stock by category
        context['stock_by_category'] = Category.objects.annotate(total_stock=Sum('product__available_quantity')).order_by('-total_stock')

        return context

class ProductsAnalyticsView(TemplateView):
    template_name = 'analytics/products.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        last_year = timezone.now().date() - timedelta(days=365)

        # Top products by sales
        context['top_products'] = Product.objects.annotate(
            sales_count=Count('orderitem', filter=Q(orderitem__order__status='completed')),
            total_revenue=Sum('orderitem__order__total', filter=Q(orderitem__order__status='completed'))
        ).order_by('-sales_count')[:10]

        # Product performance over time
        context['monthly_sales'] = OrderItem.objects.filter(order__status='completed', order__created_at__gte=last_year).annotate(
            month=TruncMonth('order__created_at')
        ).values('month', 'product__products_name').annotate(count=Count('id')).order_by('month')

        return context

class RevenueAnalyticsView(TemplateView):
    template_name = 'analytics/revenue.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        last_year = timezone.now().date() - timedelta(days=365)

        # Revenue metrics
        context['total_revenue'] = Order.objects.filter(status='completed').aggregate(total=Sum('total'))['total'] or 0
        context['monthly_revenue'] = Order.objects.filter(status='completed', created_at__gte=last_year).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(total=Sum('total')).order_by('month')

        # Revenue by category
        context['revenue_by_category'] = Category.objects.annotate(
            total_revenue=Sum('product__orderitem__order__total', filter=Q(product__orderitem__order__status='completed'))
        ).order_by('-total_revenue')

        # Charts data
        context['monthly_revenue_data'] = {
            'labels': [item['month'].strftime('%b %Y') for item in context['monthly_revenue']],
            'data': [float(item['total']) for item in context['monthly_revenue']],
        }

        return context

class CustomerListView(ListView):
    model = User
    template_name = 'analytics/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20

    def get_queryset(self):
        queryset = User.objects.annotate(
            order_count=Count('order'),
            total_spent=Sum('order__total', filter=Q(order__status='completed')),
            last_order_date=Max('order__created_at')
        ).order_by('-total_spent')
        return queryset

class CustomerDetailView(DetailView):
    model = User
    template_name = 'analytics/customer_detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.object

        # Customer history
        context['orders'] = Order.objects.filter(user=customer).order_by('-created_at')
        context['total_spent'] = context['orders'].filter(status='completed').aggregate(total=Sum('total'))['total'] or 0
        context['order_count'] = context['orders'].count()
        context['favorite_products'] = Product.objects.filter(orderitem__order__user=customer).annotate(
            purchase_count=Count('orderitem')
        ).order_by('-purchase_count')[:5]

        # Recent activity
        last_30_days = timezone.now().date() - timedelta(days=30)
        context['recent_orders'] = context['orders'].filter(created_at__gte=last_30_days)

        return context