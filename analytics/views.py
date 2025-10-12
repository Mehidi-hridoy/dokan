from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Count, Q, Sum, F
from orders.models import Order, OrderItem
from products.models import Product
from inventory.models import Inventory
from promotions.models import Promotion, PromotionUsage
from django import forms
from django.core.exceptions import ValidationError
from .models import Customer
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from django.http import JsonResponse

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

@login_required
def analytics_dashboard(request):
    form = DateFilterForm(request.GET or None)
    today = timezone.now().date()
    start_date = today
    end_date = today

    if form.is_valid():
        period = form.cleaned_data['period']
        if period == 'yesterday':
            start_date = today - timedelta(days=1)
            end_date = start_date
        elif period == 'last_7_days':
            start_date = today - timedelta(days=6)
            end_date = today
        elif period == 'custom':
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
    
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    prev_start = start_datetime - (end_datetime - start_datetime + timedelta(days=1))
    prev_end = end_datetime - (end_datetime - start_datetime + timedelta(days=1))

    # Staff filter
    staff_filter = Q()
    if request.user.user_type == 'admin' and not request.user.is_superuser:
        staff_filter = Q(assigned_staff=request.user)

    # Order analytics
    order_stats = {
        'total': Order.objects.filter(staff_filter & Q(created_at__range=(start_datetime, end_datetime))).count(),
        'confirmed': Order.objects.confirmed_orders().filter(staff_filter & Q(created_at__range=(start_datetime, end_datetime))).count(),
        'rejected': Order.objects.rejected_orders().filter(staff_filter & Q(created_at__range=(start_datetime, end_datetime))).count(),
        'hold': Order.objects.hold_orders().filter(staff_filter & Q(created_at__range=(start_datetime, end_datetime))).count(),
        'pending': Order.objects.pending_orders().filter(staff_filter & Q(created_at__range=(start_datetime, end_datetime))).count(),
        'processed': Order.objects.processed_orders().filter(staff_filter & Q(created_at__range=(start_datetime, end_datetime))).count(),
        'revenue': Order.objects.filter(staff_filter & Q(created_at__range=(start_datetime, end_datetime))).aggregate(total=Sum('total'))['total'] or 0,
    }
    prev_order_stats = {
        'total': Order.objects.filter(staff_filter & Q(created_at__range=(prev_start, prev_end))).count(),
        'confirmed': Order.objects.confirmed_orders().filter(staff_filter & Q(created_at__range=(prev_start, prev_end))).count(),
        'rejected': Order.objects.rejected_orders().filter(staff_filter & Q(created_at__range=(prev_start, prev_end))).count(),
        'hold': Order.objects.hold_orders().filter(staff_filter & Q(created_at__range=(prev_start, prev_end))).count(),
        'pending': Order.objects.pending_orders().filter(staff_filter & Q(created_at__range=(prev_start, prev_end))).count(),
        'processed': Order.objects.processed_orders().filter(staff_filter & Q(created_at__range=(prev_start, prev_end))).count(),
        'revenue': Order.objects.filter(staff_filter & Q(created_at__range=(prev_start, prev_end))).aggregate(total=Sum('total'))['total'] or 0,
    }

    def get_change(current, previous):
        if previous == 0:
            return "No previous data"
        change_pct = ((current - previous) / previous) * 100
        return f"{change_pct:+.2f}%"

    # Order items analytics
    order_items = OrderItem.objects.filter(order__created_at__range=(start_datetime, end_datetime), order__in=Order.objects.filter(staff_filter))
    items_stats = {
        'total_items': order_items.aggregate(total=Sum('quantity'))['total'] or 0,
        'top_products': order_items.values('product__name').annotate(total_qty=Sum('quantity')).order_by('-total_qty')[:5],
        'delivery_status': order_items.values('delivery_status').annotate(count=Count('id')).order_by('-count'),
    }
    prev_items_stats = {
        'total_items': OrderItem.objects.filter(order__created_at__range=(prev_start, prev_end), order__in=Order.objects.filter(staff_filter)).aggregate(total=Sum('quantity'))['total'] or 0,
    }

    # Products analytics
    products_stats = {
        'total': Product.objects.filter(staff_filter).count(),
        'active': Product.objects.filter(staff_filter & Q(is_active=True)).count(),
        'inactive': Product.objects.filter(staff_filter & Q(is_active=False)).count(),
        'top_categories': Product.objects.filter(staff_filter).values('category__name').annotate(count=Count('id')).order_by('-count')[:5],
    }

    # Inventory analytics
    inventory_stats = {
        'low_stock': Inventory.objects.filter(staff_filter & Q(quantity__lte=F('low_stock_threshold'))).count(),
        'total_value': Inventory.objects.filter(staff_filter).aggregate(total=Sum(F('quantity') * F('product__price')))['total'] or 0,
    }

    # Promotions analytics
    promotions_stats = {
        'active': Promotion.objects.filter(staff_filter & Q(is_active=True, start_date__lte=timezone.now(), end_date__gte=timezone.now())).count(),
        'total_discount': Order.objects.filter(staff_filter & Q(created_at__range=(start_datetime, end_datetime))).aggregate(total=Sum('discount_amount'))['total'] or 0,
        'usage_count': PromotionUsage.objects.filter(staff_filter & Q(used_at__range=(start_datetime, end_datetime))).count(),
    }

    context = {
        'form': form,
        'start_date': start_date,
        'end_date': end_date,
        'order_stats': order_stats,
        'order_changes': {k: get_change(v, prev_order_stats[k]) for k, v in order_stats.items()},
        'items_stats': items_stats,
        'items_changes': {'total_items': get_change(items_stats['total_items'], prev_items_stats['total_items'])},
        'products_stats': products_stats,
        'inventory_stats': inventory_stats,
        'promotions_stats': promotions_stats,
    }

    return render(request, 'analytics/dashboard.html', context)



@login_required
def customer_analytics(request):
    # Get customer statistics
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
    
    return render(request, 'analytics/customers.html', context)

@login_required
def customer_detail(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    orders = customer.orders.all().order_by('-created_at')
    
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
            customer.save()
            messages.warning(request, f'{customer.name} has been marked as fraudulent.')
        elif action == 'unblock':
            customer.is_fraudulent = False
            customer.save()
            messages.success(request, f'{customer.name} has been unblocked.')
        elif action == 'convert':
            # Convert guest to registered user logic
            pass
    
    return redirect('customer_detail', customer_id=customer_id)

# Guest Checkout Handler
def handle_guest_checkout(order_data):
    """
    Handle guest checkout - create or get customer and link to order
    """
    
    email = order_data.get('email')
    phone = order_data.get('phone_number')
    name = order_data.get('customer_name')
    
    if email and phone:
        # Get or create customer
        customer, created = Customer.objects.get_or_create_guest_customer(
            email=email,
            phone=phone,
            name=name
        )
        
        return customer
    return None

@receiver(post_save, sender=Order)
def update_customer_on_order_save(sender, instance, **kwargs):
    """
    Update customer statistics when an order is saved
    """
    if instance.customer:
        instance.customer.update_customer_stats()
    
    # If no customer linked but we have customer info, try to find/create one
    elif not instance.customer and instance.email and instance.phone_number:
        from customers.models import Customer
        customer, created = Customer.objects.get_or_create_guest_customer(
            email=instance.email,
            phone=instance.phone_number,
            name=instance.customer_name
        )
        instance.customer = customer
        instance.save(update_fields=['customer'])

# API view for customer search (for AJAX requests)
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

