from django.views.generic import TemplateView, ListView, DetailView
from django.db.models import Sum, Count, Avg, Q, Max, F, ExpressionWrapper, fields
from django.db.models.functions import TruncDay, TruncMonth
from users.models import User
from orders.models import Order, OrderItem
from products.models import Product, Category
from inventory.models import Inventory # Assuming Inventory is imported here
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db.models import Count, Sum, F, Q, ExpressionWrapper, DecimalField


# Helper Expression for Available Stock (Total - Reserved)
AVAILABLE_STOCK = F('quantity') - F('reserved_quantity')



class AnalyticsDashboard(TemplateView):
    template_name = 'analytics/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)

        # Overall stats
        context['total_revenue'] = Order.objects.filter(order_status='confirmed').aggregate(total=Sum('total'))['total'] or 0
        context['total_orders'] = Order.objects.count()
        context['average_order_value'] = Order.objects.filter(order_status='confirmed').aggregate(avg=Avg('total'))['avg'] or 0
        
        # Count unique customers by phone number
        # For registered users: count unique users who placed orders
        unique_registered_customers = Order.objects.filter(
            user__isnull=False
        ).values('user').distinct().count()
        context['total_registered_customers'] = unique_registered_customers
        
        # For guest customers: count unique phone numbers (excluding null/empty)
        guest_customers_count = Order.objects.filter(
            user__isnull=True
        ).exclude(phone_number__isnull=True).exclude(phone_number='').values('phone_number').distinct().count()
        context['total_guest_customers'] = guest_customers_count
        
        # Total unique customers (registered + guest by phone)
        context['total_customers'] = context['total_registered_customers'] + context['total_guest_customers']

        # Count unique phone numbers across all orders (for debugging)
        context['unique_phone_numbers_total'] = Order.objects.exclude(
            phone_number__isnull=True
        ).exclude(phone_number='').values('phone_number').distinct().count()
        
        context['unique_phone_numbers_registered'] = Order.objects.filter(
            user__isnull=False
        ).exclude(phone_number__isnull=True).exclude(phone_number='').values('phone_number').distinct().count()
        
        context['unique_phone_numbers_guest'] = Order.objects.filter(
            user__isnull=True
        ).exclude(phone_number__isnull=True).exclude(phone_number='').values('phone_number').distinct().count()

        # Order statuses
        context['confirmed_orders'] = Order.objects.filter(order_status='confirmed').count()
        context['pending_orders'] = Order.objects.filter(order_status='pending').count()
        context['processed_orders'] = Order.objects.filter(order_status='processed').count()
        context['rejected_orders'] = Order.objects.filter(order_status='rejected').count()
        context['hold_orders'] = Order.objects.filter(order_status='hold').count()

        # Courier statuses
        context['out_for_delivery_orders'] = Order.objects.filter(courier_status='out_for_delivery').count()
        context['delivered_orders'] = Order.objects.filter(courier_status='delivered').count()

        # Inventory stats
        inventory_qs = Inventory.objects.annotate(available_stock=AVAILABLE_STOCK)
        
        context['total_stock'] = inventory_qs.aggregate(total=Sum('available_stock'))['total'] or 0
        context['in_stock_items'] = inventory_qs.filter(available_stock__gt=0).count()
        context['low_stock_items'] = inventory_qs.filter(
            available_stock__gt=0,
            available_stock__lte=F('low_stock_threshold')
        ).count()
        context['out_of_stock_items'] = inventory_qs.filter(available_stock__lte=0).count()

        # Recent activity (last 30 days)
        context['new_customers_last_30'] = User.objects.filter(date_joined__gte=last_30_days).count()
        context['revenue_last_30'] = Order.objects.filter(order_status='confirmed', created_at__gte=last_30_days).aggregate(total=Sum('total'))['total'] or 0

        # Order type statistics
        context['guest_orders_count'] = Order.objects.filter(user__isnull=True).count()
        context['registered_orders_count'] = Order.objects.filter(user__isnull=False).count()

        # Sample data for debugging
        context['sample_phone_numbers'] = list(Order.objects.exclude(
            phone_number__isnull=True
        ).exclude(phone_number='').values('customer_name', 'phone_number', 'user__username')[:10])

        # Charts data (daily sales for last 30 days)
        daily_sales = Order.objects.filter(order_status='confirmed', created_at__gte=last_30_days).annotate(
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
        context['total_revenue'] = Order.objects.filter(order_status='confirmed').aggregate(total=Sum('total'))['total'] or 0
        context['monthly_revenue'] = Order.objects.filter(order_status='confirmed', created_at__gte=last_year).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(total=Sum('total')).order_by('month')

        # Top customers by spend
        context['top_customers'] = User.objects.annotate(
            total_spent=Sum('orders__total', filter=Q(orders__order_status='confirmed'))
        ).order_by(F('total_spent').desc(nulls_last=True))[:10]

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
        context['order_statuses'] = Order.objects.values('order_status').annotate(count=Count('id')).order_by('-count')

        # Orders over time
        last_30_days = timezone.now().date() - timedelta(days=30)
        context['daily_orders'] = Order.objects.filter(created_at__gte=last_30_days).annotate(
            day=TruncDay('created_at')
        ).values('day').annotate(count=Count('id')).order_by('day')

        # Pending, processed, hold, confirmed, rejected
        context['pending_orders'] = Order.objects.filter(order_status='pending').count()
        context['processed_orders'] = Order.objects.filter(order_status='processed').count()
        context['hold_orders'] = Order.objects.filter(order_status='hold').count()
        context['confirmed_orders'] = Order.objects.filter(order_status='confirmed').count()
        context['rejected_orders'] = Order.objects.filter(order_status='rejected').count()

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

        # Annotate Inventory with available stock
        inventory_qs = Inventory.objects.annotate(
            available_stock=F('quantity') - F('reserved_quantity')
        )

        # Total products
        context['total_products'] = Product.objects.count()

        # Total stock
        context['total_stock'] = inventory_qs.aggregate(
            total=Sum('available_stock')
        )['total'] or 0

        # Low stock products (0 < available_stock <= low_stock_threshold)
        context['low_stock'] = inventory_qs.filter(
            available_stock__gt=0,
            available_stock__lte=F('low_stock_threshold')
        ).count()

        # Out of stock products (available_stock <= 0)
        context['out_of_stock'] = inventory_qs.filter(
            available_stock__lte=0
        ).count()

        # Top low stock products (annotate Product with available stock)
        context['low_stock_products'] = Product.objects.annotate(
            available_stock=Sum(
                F('inventory__quantity') - F('inventory__reserved_quantity')
            )
        ).filter(
            available_stock__gt=0,
            available_stock__lte=F('inventory__low_stock_threshold')
        ).order_by('available_stock')[:10]

        # Stock by category
        context['stock_by_category'] = Category.objects.annotate(
            total_stock=Sum(
                F('products__inventory__quantity') - F('products__inventory__reserved_quantity')
            )
        ).order_by(F('total_stock').desc(nulls_last=True))

        return context



class ProductsAnalyticsView(TemplateView):
    template_name = 'analytics/products.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        last_year = timezone.now().date() - timedelta(days=365)

        # Top products by sales
        context['top_products'] = Product.objects.annotate(
            sales_count=Count(
                'order_items',  # related_name from OrderItem model
                filter=Q(order_items__order__order_status='confirmed')
            ),
            total_revenue=Sum(
                ExpressionWrapper(
                    F('order_items__quantity') * 
                    (F('order_items__product__sale_price') + 0),  # fallback to current_price if sale_price is null
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                filter=Q(order_items__order__order_status='confirmed')
            )
        ).order_by('-sales_count')[:10]

        # Product performance over time (monthly sales)
        context['monthly_sales'] = (
            OrderItem.objects.filter(
                order__order_status='confirmed', 
                order__created_at__gte=last_year
            )
            .annotate(month=TruncMonth('order__created_at'))
            .values('month', 'product__products_name')
            .annotate(count=Count('id'))
            .order_by('month')
        )

        return context




class RevenueAnalyticsView(TemplateView):
    template_name = 'analytics/revenue.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        last_year = timezone.now().date() - timedelta(days=365)

        # Total revenue
        context['total_revenue'] = Order.objects.filter(order_status='confirmed').aggregate(
            total=Sum('total')
        )['total'] or 0

        # Monthly revenue
        context['monthly_revenue'] = (
            Order.objects.filter(order_status='confirmed', created_at__gte=last_year)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(total=Sum('total'))
            .order_by('month')
        )

        # Revenue by category (sum quantity * price per product)
        revenue_expr = ExpressionWrapper(
            F('products__order_items__quantity') *
            (F('products__sale_price') + 0),  # fallback to current_price if needed
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )

        context['revenue_by_category'] = Category.objects.annotate(
            total_revenue=Sum(
                revenue_expr,
                filter=Q(products__order_items__order__order_status='confirmed')
            )
        ).order_by(F('total_revenue').desc(nulls_last=True))

        # Prepare chart data
        context['monthly_revenue_data'] = {
            'labels': [item['month'].strftime('%b %Y') for item in context['monthly_revenue']],
            'data': [float(item['total']) for item in context['monthly_revenue']],
        }

        return context






class CustomerListView(ListView):
    template_name = 'analytics/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20

    def get_queryset(self):
        from orders.models import Order
        from django.core.paginator import Paginator
        
        # Get all unique customers from orders
        all_customers = []
        
        # Process registered users
        registered_orders = Order.objects.filter(
            user__isnull=False
        ).select_related('user').values(
            'user__id', 'user__username', 'user__email', 
            'user__first_name', 'user__last_name'
        ).annotate(
            order_count=Count('id'),
            total_spent=Sum('total', filter=Q(order_status='confirmed')),
            last_order_date=Max('created_at')
        ).filter(order_count__gt=0)
        
        for order in registered_orders:
            display_name = order['user__username'] or order['user__email'] or f"User {order['user__id']}"
            all_customers.append({
                'id': order['user__id'],
                'display_name': display_name,
                'email': order['user__email'],
                'phone_number': '',
                'order_count': order['order_count'],
                'total_spent': order['total_spent'] or 0,
                'last_order_date': order['last_order_date'],
                'customer_type': 'registered'
            })
        
        # Process guest customers
        guest_orders = Order.objects.filter(
            user__isnull=True
        ).values(
            'customer_name', 'phone_number', 'email'
        ).annotate(
            order_count=Count('id'),
            total_spent=Sum('total', filter=Q(order_status='confirmed')),
            last_order_date=Max('created_at')
        ).filter(order_count__gt=0)
        
        for guest in guest_orders:
            display_name = guest['customer_name'] or 'Guest Customer'
            all_customers.append({
                'id': f"guest_{guest['phone_number'] or guest['email'] or guest['customer_name']}",
                'display_name': display_name,
                'email': guest['email'],
                'phone_number': guest['phone_number'],
                'order_count': guest['order_count'],
                'total_spent': guest['total_spent'] or 0,
                'last_order_date': guest['last_order_date'],
                'customer_type': 'guest'
            })
        
        # Sort by total spent
        all_customers.sort(key=lambda x: x['total_spent'], reverse=True)
        return all_customers

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_customers'] = len(self.object_list)
        context['registered_customers_count'] = len([c for c in self.object_list if c['customer_type'] == 'registered'])
        context['guest_customers_count'] = len([c for c in self.object_list if c['customer_type'] == 'guest'])
        return context


class CustomerDetailView(DetailView):
    model = User
    template_name = 'analytics/customer_detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.object

        # Customer order history
        context['orders'] = Order.objects.filter(user=customer).order_by('-created_at')
        context['total_spent'] = (
            context['orders']
            .filter(order_status='confirmed')
            .aggregate(total=Sum('total'))['total'] or 0
        )
        context['order_count'] = context['orders'].count()

        # Favorite products — using correct related name: order_items
        context['favorite_products'] = (
            Product.objects.filter(order_items__order__user=customer)
            .annotate(
                purchase_count=Sum(
                    'order_items__quantity',
                    filter=Q(order_items__order__order_status='confirmed')
                )
            )
            .order_by(F('purchase_count').desc(nulls_last=True))[:5]
        )

        # Recent orders (last 30 days)
        last_30_days = timezone.now().date() - timedelta(days=30)
        context['recent_orders'] = context['orders'].filter(created_at__gte=last_30_days)

        return context
