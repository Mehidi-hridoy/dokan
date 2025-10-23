from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm
from orders.models import Order, OrderItem
from products.models import Product
from django.db.models import Sum, Count, Q
from datetime import datetime, timedelta
from django.utils import timezone

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Auto-login after registration
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome {user.username}! Your account has been created successfully.')
                return redirect('products:home')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'users/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('products:home')
    
    return render(request, 'users/login.html')




@login_required
def profile(request):
    customer = request.user
    
    # Get customer order history
    orders = Order.objects.filter(user=customer).order_by('-created_at')
    
    # Calculate total spent (only confirmed orders) - using 'total' field
    total_spent = (
        orders.filter(order_status='confirmed')
        .aggregate(total=Sum('total'))['total'] or 0
    )
    
    order_count = orders.count()

    # Favorite products
    favorite_products = (
        Product.objects.filter(order_items__order__user=customer)
        .annotate(
            purchase_count=Sum(
                'order_items__quantity',
                filter=Q(order_items__order__order_status='confirmed')
            )
        )
        .order_by('-purchase_count')[:5]
    )

    # Recent orders (last 30 days)
    last_30_days = timezone.now().date() - timedelta(days=30)
    recent_orders = orders.filter(created_at__gte=last_30_days)
    
    # Order status breakdown
    status_breakdown = orders.values('order_status').annotate(
        count=Count('id')
    ).order_by('-count')

    context = {
        'customer': customer,
        'orders': orders,
        'total_spent': total_spent,
        'order_count': order_count,
        'favorite_products': favorite_products,
        'recent_orders': recent_orders,
        'status_breakdown': status_breakdown,
    }
    
    return render(request, 'users/profile.html', context)

