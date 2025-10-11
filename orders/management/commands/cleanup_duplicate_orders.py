from django.core.management.base import BaseCommand
from orders.models import Order
from django.db.models import Count

class Command(BaseCommand):
    help = 'Clean up duplicate pending orders'

    def handle(self, *args, **options):
        # Find users with multiple pending orders
        duplicate_orders = Order.objects.filter(
            order_status='pending'
        ).values('user').annotate(
            count=Count('id')
        ).filter(count__gt=1)

        for item in duplicate_orders:
            user_id = item['user']
            if user_id:  # Only for authenticated users
                # Get all pending orders for this user, ordered by creation date
                orders = Order.objects.filter(
                    user_id=user_id,
                    order_status='pending'
                ).order_by('-created_at')
                
                # Keep the most recent one, delete others
                latest_order = orders.first()
                orders_to_delete = orders.exclude(id=latest_order.id)
                
                deleted_count = orders_to_delete.count()
                orders_to_delete.delete()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Cleaned up {deleted_count} duplicate orders for user {user_id}. '
                        f'Kept order #{latest_order.order_number}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS('Duplicate order cleanup completed!')
        )