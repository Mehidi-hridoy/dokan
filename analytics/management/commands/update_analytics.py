# analytics/management/commands/update_analytics.py
from django.core.management.base import BaseCommand
from analytics.models import SalesSummary, InventorySummary, CustomerSummary
from django.utils import timezone
from orders.models import Order
from products.models import Product
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Update daily analytics summaries'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)

        # Sales Summary
        sales_data = Order.objects.filter(status='completed', created_at__date=today).aggregate(
            total_revenue=Sum('total'), total_orders=Count('id'), avg_order_value=Avg('total')
        )
        SalesSummary.objects.update_or_create(
            date=today,
            defaults={
                'total_revenue': sales_data['total_revenue'] or 0,
                'total_orders': sales_data['total_orders'] or 0,
                'average_order_value': sales_data['avg_order_value'] or 0,
                'completed_orders': Order.objects.filter(status='completed', created_at__date=today).count(),
                'pending_orders': Order.objects.filter(status='pending', created_at__date=today).count(),
                'processing_orders': Order.objects.filter(status='processing', created_at__date=today).count(),
                'canceled_orders': Order.objects.filter(status='canceled', created_at__date=today).count(),
            }
        )

        # Inventory Summary
        InventorySummary.objects.update_or_create(
            date=today,
            defaults={
                'total_stock': Product.objects.aggregate(total=Sum('available_quantity'))['total'] or 0,
                'in_stock_items': Product.objects.filter(is_in_stock=True).count(),
                'low_stock_items': Product.objects.filter(available_quantity__lt=10, available_quantity__gt=0).count(),
                'out_of_stock_items': Product.objects.filter(available_quantity=0).count(),
                'on_delivery': Order.objects.filter(status='on_delivery', created_at__date=today).count(),
            }
        )

        # Customer Summary
        CustomerSummary.objects.update_or_create(
            date=today,
            defaults={
                'total_customers': User.objects.count(),
                'new_customers': User.objects.filter(date_joined__gte=last_30_days).count(),
                'repeat_customers': User.objects.filter(order__created_at__date=today).distinct().count(),
                'active_customers': User.objects.filter(order__created_at__gte=last_30_days).distinct().count(),
            }
        )
        self.stdout.write(self.style.SUCCESS('Analytics summaries updated successfully.'))