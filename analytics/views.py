from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from orders.models import Order
from django.db.models import Count, Q, Sum

@login_required
def order_overview_dashboard(request):
    # Timezone-aware date filters
    today = timezone.now().date()
    today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    today_end = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))
    yesterday_start = today_start - timedelta(days=1)
    yesterday_end = today_end - timedelta(days=1)

    # Staff filtering base (apply to all queries below)
    staff_filter = Q()
    if request.user.user_type == 'admin' and not request.user.is_superuser:
        # staff_filter = Q(assigned_staff=request.user)  # Uncomment if you added the assigned_staff field
        pass  # Remove or adjust if using another logic (e.g., Q(user__vendor=request.user) if tied to vendors)

    # Today's stats using manager methods + filters
    today_stats = {
        'total': Order.objects.filter(staff_filter & Q(created_at__range=(today_start, today_end))).count(),
        'pending': Order.objects.pending_orders().filter(staff_filter & Q(created_at__range=(today_start, today_end))).count(),
        'processed': Order.objects.processed_orders().filter(staff_filter & Q(created_at__range=(today_start, today_end))).count(),
        'on_delivery': Order.objects.on_delivery_orders().filter(staff_filter & Q(created_at__range=(today_start, today_end))).count(),
        'partial_delivery': Order.objects.partial_delivery_orders().filter(staff_filter & Q(created_at__range=(today_start, today_end))).count(),
        'delivered': Order.objects.delivered_orders().filter(staff_filter & Q(created_at__range=(today_start, today_end))).count(),
        'cancelled': Order.objects.cancelled_orders().filter(staff_filter & Q(created_at__range=(today_start, today_end))).count(),
        'returned': Order.objects.returned_orders().filter(staff_filter & Q(created_at__range=(today_start, today_end))).count(),
        'revenue': Order.objects.filter(staff_filter & Q(created_at__range=(today_start, today_end))).aggregate(total_revenue=Sum('total'))['total_revenue'] or 0,
    }

    # Yesterday's stats
    yesterday_stats = {
        'total': Order.objects.filter(staff_filter & Q(created_at__range=(yesterday_start, yesterday_end))).count(),
        'pending': Order.objects.pending_orders().filter(staff_filter & Q(created_at__range=(yesterday_start, yesterday_end))).count(),
        'processed': Order.objects.processed_orders().filter(staff_filter & Q(created_at__range=(yesterday_start, yesterday_end))).count(),
        'on_delivery': Order.objects.on_delivery_orders().filter(staff_filter & Q(created_at__range=(yesterday_start, yesterday_end))).count(),
        'partial_delivery': Order.objects.partial_delivery_orders().filter(staff_filter & Q(created_at__range=(yesterday_start, yesterday_end))).count(),
        'delivered': Order.objects.delivered_orders().filter(staff_filter & Q(created_at__range=(yesterday_start, yesterday_end))).count(),
        'cancelled': Order.objects.cancelled_orders().filter(staff_filter & Q(created_at__range=(yesterday_start, yesterday_end))).count(),
        'returned': Order.objects.returned_orders().filter(staff_filter & Q(created_at__range=(yesterday_start, yesterday_end))).count(),
        'revenue': Order.objects.filter(staff_filter & Q(created_at__range=(yesterday_start, yesterday_end))).aggregate(total_revenue=Sum('total'))['total_revenue'] or 0,
    }

    # Helper for change message (updated to handle 0/0 as "No previous data" if no yesterday activity)
    def get_change(current, previous):
        if previous == 0:
            return "No previous data"
        change_pct = ((current - previous) / previous) * 100
        return f"{change_pct:+.2f}% from yesterday"

    # Context assembly
    context = {
        'today': today,
        'total_orders': today_stats['total'],
        'total_change': get_change(today_stats['total'], yesterday_stats['total']),
        'pending_orders': today_stats['pending'],
        'pending_change': get_change(today_stats['pending'], yesterday_stats['pending']),
        'processed_orders': today_stats['processed'],
        'processed_change': get_change(today_stats['processed'], yesterday_stats['processed']),
        'on_delivery_orders': today_stats['on_delivery'],
        'on_delivery_change': get_change(today_stats['on_delivery'], yesterday_stats['on_delivery']),
        'partial_delivery_orders': today_stats['partial_delivery'],
        'partial_delivery_change': get_change(today_stats['partial_delivery'], yesterday_stats['partial_delivery']),
        'delivered_orders': today_stats['delivered'],
        'delivered_change': get_change(today_stats['delivered'], yesterday_stats['delivered']),
        'cancelled_orders': today_stats['cancelled'],
        'cancelled_change': get_change(today_stats['cancelled'], yesterday_stats['cancelled']),
        'returned_orders': today_stats['returned'],
        'returned_change': get_change(today_stats['returned'], yesterday_stats['returned']),
        'today_revenue': today_stats['revenue'],
        'revenue_change': get_change(today_stats['revenue'], yesterday_stats['revenue']),
    }

    return render(request, 'analytics/order_overview.html', context)