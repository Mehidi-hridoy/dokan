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
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        last_90_days = today - timedelta(days=90)
        last_year = today - timedelta(days=365)

        # Overall sales metrics
        confirmed_orders = Order.objects.filter(order_status='confirmed')
        context['total_revenue'] = confirmed_orders.aggregate(total=Sum('total'))['total'] or 0
        context['total_orders'] = Order.objects.count()
        context['average_order_value'] = confirmed_orders.aggregate(avg=Avg('total'))['avg'] or 0
        
        # Recent performance
        context['recent_revenue_30d'] = confirmed_orders.filter(
            created_at__gte=last_30_days
        ).aggregate(total=Sum('total'))['total'] or 0
        
        context['recent_orders_30d'] = Order.objects.filter(
            created_at__gte=last_30_days
        ).count()

        # Monthly revenue trend
        context['monthly_revenue'] = Order.objects.filter(
            order_status='confirmed', 
            created_at__gte=last_year
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('total'),
            order_count=Count('id')
        ).order_by('month')

        # Top customers by spend (with order count)
        context['top_customers'] = User.objects.annotate(
            total_spent=Sum('orders__total', filter=Q(orders__order_status='confirmed')),
            order_count=Count('orders', filter=Q(orders__order_status='confirmed'))
        ).filter(total_spent__isnull=False).order_by(F('total_spent').desc(nulls_last=True))[:10]

        # Sales by payment method
        context['sales_by_payment_method'] = Order.objects.filter(
            order_status='confirmed'
        ).values('payment_method').annotate(
            total_revenue=Sum('total'),
            order_count=Count('id')
        ).order_by('-total_revenue')

        # Daily sales for last 30 days
        context['daily_sales'] = Order.objects.filter(
            order_status='confirmed',
            created_at__gte=last_30_days
        ).annotate(
            day=TruncDay('created_at')
        ).values('day').annotate(
            total=Sum('total'),
            order_count=Count('id')
        ).order_by('day')

        # Best selling products
        context['best_selling_products'] = Product.objects.annotate(
            total_sold=Sum('order_items__quantity', filter=Q(order_items__order__order_status='confirmed')),
            total_revenue=Sum(
                F('order_items__quantity') * F('order_items__order__total') / F('order_items__order__items__quantity'),
                filter=Q(order_items__order__order_status='confirmed')
            )
        ).filter(total_sold__gt=0).order_by('-total_sold')[:10]

        # Revenue growth (current month vs previous month)
        current_month_start = today.replace(day=1)
        prev_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        prev_month_end = current_month_start - timedelta(days=1)
        
        current_month_revenue = confirmed_orders.filter(
            created_at__gte=current_month_start
        ).aggregate(total=Sum('total'))['total'] or 0
        
        prev_month_revenue = confirmed_orders.filter(
            created_at__gte=prev_month_start,
            created_at__lte=prev_month_end
        ).aggregate(total=Sum('total'))['total'] or 0
        
        context['revenue_growth'] = 0
        if prev_month_revenue > 0:
            context['revenue_growth'] = ((current_month_revenue - prev_month_revenue) / prev_month_revenue) * 100

        # Charts data
        context['monthly_revenue_data'] = {
            'labels': [item['month'].strftime('%b %Y') for item in context['monthly_revenue']],
            'data': [float(item['total']) for item in context['monthly_revenue']],
            'order_counts': [item['order_count'] for item in context['monthly_revenue']]
        }

        context['daily_sales_data'] = {
            'labels': [item['day'].strftime('%m/%d') for item in context['daily_sales']],
            'revenue': [float(item['total']) for item in context['daily_sales']],
            'orders': [item['order_count'] for item in context['daily_sales']]
        }

        context['payment_method_data'] = {
            'labels': [item['payment_method'] or 'Unknown' for item in context['sales_by_payment_method']],
            'revenue': [float(item['total_revenue']) for item in context['sales_by_payment_method']],
            'orders': [item['order_count'] for item in context['sales_by_payment_method']]
        }

        return context


class OrdersAnalyticsView(TemplateView):
    template_name = 'analytics/orders.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        last_7_days = today - timedelta(days=7)

        # Total orders and revenue
        context['total_orders'] = Order.objects.count()
        context['total_revenue'] = Order.objects.filter(
            order_status='confirmed'
        ).aggregate(total=Sum('total'))['total'] or 0
        context['average_order_value'] = Order.objects.filter(
            order_status='confirmed'
        ).aggregate(avg=Avg('total'))['avg'] or 0

        # Order statuses breakdown
        context['order_statuses'] = Order.objects.values('order_status').annotate(
            count=Count('id')
        ).order_by('-count')

        # Orders over time
        context['daily_orders'] = Order.objects.filter(
            created_at__gte=last_30_days
        ).annotate(
            day=TruncDay('created_at')
        ).values('day').annotate(
            count=Count('id'),
            revenue=Sum('total', filter=Q(order_status='confirmed'))
        ).order_by('day')

        # Detailed order status counts
        context['pending_orders'] = Order.objects.filter(order_status='pending').count()
        context['processed_orders'] = Order.objects.filter(order_status='processed').count()
        context['hold_orders'] = Order.objects.filter(order_status='hold').count()
        context['confirmed_orders'] = Order.objects.filter(order_status='confirmed').count()
        context['rejected_orders'] = Order.objects.filter(order_status='rejected').count()

        # Courier status counts
        context['out_for_delivery_orders'] = Order.objects.filter(
            courier_status='out_for_delivery'
        ).count()
        context['delivered_orders'] = Order.objects.filter(courier_status='delivered').count()
        context['in_transit_orders'] = Order.objects.filter(courier_status='in_transit').count()

        # Payment status counts
        context['paid_orders'] = Order.objects.filter(payment_status='paid').count()
        context['pending_payment_orders'] = Order.objects.filter(payment_status='pending').count()
        context['failed_payment_orders'] = Order.objects.filter(payment_status='failed').count()

        # Recent orders (last 7 days)
        context['recent_orders_count'] = Order.objects.filter(
            created_at__gte=last_7_days
        ).count()
        context['recent_revenue'] = Order.objects.filter(
            created_at__gte=last_7_days,
            order_status='confirmed'
        ).aggregate(total=Sum('total'))['total'] or 0

        # Payment method breakdown
        context['payment_methods'] = Order.objects.exclude(
            payment_method__isnull=True
        ).values('payment_method').annotate(
            count=Count('id'),
            revenue=Sum('total', filter=Q(order_status='confirmed'))
        ).order_by('-count')

        # Charts data
        context['daily_orders_data'] = {
            'labels': [item['day'].strftime('%m/%d') for item in context['daily_orders']],
            'data': [item['count'] for item in context['daily_orders']],
            'revenue_data': [float(item['revenue'] or 0) for item in context['daily_orders']]
        }

        # Order status data for pie chart
        context['order_status_data'] = {
            'labels': [status['order_status'].title() for status in context['order_statuses']],
            'data': [status['count'] for status in context['order_statuses']],
            'colors': ['#f59e0b', '#f97316', '#3b82f6', '#10b981', '#ef4444']
        }

        return context



class InventoryAnalyticsView(TemplateView):
    template_name = 'analytics/inventory.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all inventory items with related product data
        inventory_items = Inventory.objects.select_related('product').filter(
            product__isnull=False
        )

        # Calculate basic metrics
        total_stock = 0
        in_stock_count = 0
        low_stock_count = 0
        out_of_stock_count = 0
        critical_stock_count = 0
        total_stock_value = 0

        # Lists to store product data
        low_stock_items = []
        out_of_stock_items = []
        high_value_items = []

        for item in inventory_items:
            available = item.available_quantity
            total_stock += available
            
            if available > 0:
                in_stock_count += 1
                # Calculate stock value
                stock_value = available * item.product.base_price
                total_stock_value += stock_value
                
                # Check for low stock
                if available <= item.low_stock_threshold:
                    low_stock_count += 1
                    low_stock_items.append({
                        'product': item.product,
                        'available_stock': available,
                        'low_stock_threshold': item.low_stock_threshold
                    })
                
                # Check for critical stock
                if available <= 5:
                    critical_stock_count += 1
                
                # Track high value items
                if stock_value > 100:  # Adjust threshold as needed
                    high_value_items.append({
                        'product': item.product,
                        'stock_value': stock_value,
                        'available_stock': available
                    })
            else:
                out_of_stock_count += 1
                out_of_stock_items.append({
                    'product': item.product,
                    'available_stock': 0
                })

        # Set context variables
        context['total_products'] = Product.objects.filter(is_active=True).count()
        context['inactive_products'] = Product.objects.filter(is_active=False).count()
        context['total_stock_value'] = total_stock_value
        context['total_stock'] = total_stock
        context['in_stock'] = in_stock_count
        context['low_stock'] = low_stock_count
        context['out_of_stock'] = out_of_stock_count
        context['critical_stock'] = critical_stock_count

        # Sort and limit lists
        context['low_stock_products'] = sorted(low_stock_items, key=lambda x: x['available_stock'])[:15]
        context['out_of_stock_products'] = out_of_stock_items[:15]
        context['high_value_products'] = sorted(high_value_items, key=lambda x: x['stock_value'], reverse=True)[:10]

        # Stock by category
        context['stock_by_category'] = []
        for category in Category.objects.all():
            category_stock = 0
            category_value = 0
            product_count = category.products.filter(is_active=True).count()
            
            for product in category.products.filter(is_active=True):
                if hasattr(product, 'inventory_reverse') and product.inventory_reverse:
                    available = product.inventory_reverse.available_quantity
                    category_stock += available
                    if available > 0:
                        category_value += available * product.base_price
            
            if category_stock > 0 or product_count > 0:
                context['stock_by_category'].append({
                    'name': category.name,
                    'total_stock': category_stock,
                    'total_value': category_value,
                    'product_count': product_count
                })
        
        # Sort by total stock
        context['stock_by_category'] = sorted(
            context['stock_by_category'], 
            key=lambda x: x['total_stock'], 
            reverse=True
        )

        # Best selling products
        context['best_selling_products'] = Product.objects.annotate(
            total_sold=Sum('order_items__quantity', filter=Q(order_items__order__order_status='confirmed'))
        ).filter(total_sold__gt=0).select_related('category').order_by('-total_sold')[:10]

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
        total_revenue_agg = Order.objects.filter(order_status='confirmed').aggregate(
            total=Sum('total')
        )
        context['total_revenue'] = total_revenue_agg['total'] or 0

        # Monthly revenue
        monthly_revenue = (
            Order.objects
            .filter(order_status='confirmed', created_at__gte=last_year)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(total=Sum('total'))
            .order_by('month')
        )
        context['monthly_revenue'] = monthly_revenue

        # DEBUG: Check OrderItem model structure
        self.debug_orderitem_structure()

        # Revenue by category - with proper field discovery
        context['revenue_by_category'] = self.get_category_revenue_with_correct_fields()

        # Prepare chart data
        monthly_labels = []
        monthly_data = []
        
        for item in monthly_revenue:
            monthly_labels.append(item['month'].strftime('%b %Y'))
            monthly_data.append(float(item['total'] or 0))

        context['monthly_revenue_data'] = {
            'labels': monthly_labels,
            'data': monthly_data,
        }

        return context

    def debug_orderitem_structure(self):
        """Debug method to check OrderItem model structure"""
        try:
            if OrderItem.objects.exists():
                sample_item = OrderItem.objects.first()
                print("=== ORDERITEM DEBUG INFO ===")
                print("OrderItem fields:", [f.name for f in sample_item._meta.get_fields()])
                print("OrderItem object:", sample_item)
                print("Available attributes:", [attr for attr in dir(sample_item) if not attr.startswith('_')])
                
                # Check what price-related fields exist
                price_fields = ['price', 'unit_price', 'sale_price', 'current_price', 'amount', 'total_price']
                for field in price_fields:
                    if hasattr(sample_item, field):
                        value = getattr(sample_item, field)
                        print(f"Field '{field}': {value} (type: {type(value)})")
                
                # Check relationships
                if hasattr(sample_item, 'product'):
                    product = sample_item.product
                    print(f"Product: {product}")
                    if product and hasattr(product, 'category'):
                        print(f"Category: {product.category}")
        except Exception as e:
            print(f"Debug error: {e}")

    def get_category_revenue_with_correct_fields(self):
        """Try different field combinations to find the correct one"""
        field_combinations = [
            # Common field name patterns
            'price',
            'unit_price', 
            'sale_price',
            'current_price',
            'amount',
            'total_price',
            'product_price',
            # Try product fields
            'product__price',
            'product__sale_price',
            'product__current_price',
        ]
        
        for field_name in field_combinations:
            try:
                result = (
                    Category.objects
                    .filter(products__order_items__order__order_status='confirmed')
                    .annotate(
                        total_revenue=Sum(
                            F('products__order_items__quantity') * 
                            F(f'products__order_items__{field_name}'),
                            output_field=DecimalField(max_digits=12, decimal_places=2)
                        )
                    )
                    .filter(total_revenue__isnull=False)
                    .order_by('-total_revenue')
                )
                
                # Check if we got non-zero results
                if result and result[0].total_revenue and result[0].total_revenue > 0:
                    print(f"SUCCESS with field: {field_name}")
                    return result
                else:
                    print(f"Field {field_name} returned zero results")
                    
            except Exception as e:
                print(f"Failed with {field_name}: {e}")
                continue
        
        # If all field combinations fail, use the manual calculation
        print("All field combinations failed, using manual calculation")
        return self.calculate_category_revenue_manually()

    def calculate_category_revenue_manually(self):
        """Manual calculation as fallback"""
        from collections import defaultdict
        import decimal
        
        category_revenue = defaultdict(decimal.Decimal)
        
        # Get all confirmed order items
        confirmed_order_items = OrderItem.objects.filter(
            order__order_status='confirmed'
        ).select_related('product', 'product__category', 'order')
        
        print(f"Found {confirmed_order_items.count()} confirmed order items")
        
        for item in confirmed_order_items:
            if item.product and item.product.category:
                category_name = item.product.category.name
                
                # Try to find the price - check multiple possible fields
                price = decimal.Decimal('0')
                
                # Try different price field names on OrderItem
                price_fields = ['price', 'unit_price', 'sale_price', 'current_price', 'amount']
                for field in price_fields:
                    if hasattr(item, field):
                        field_value = getattr(item, field)
                        if field_value:
                            price = decimal.Decimal(str(field_value))
                            break
                
                # If no price found on OrderItem, try product or calculate from order total
                if price == 0:
                    if hasattr(item, 'product') and item.product:
                        product_price_fields = ['price', 'sale_price', 'current_price']
                        for field in product_price_fields:
                            if hasattr(item.product, field):
                                field_value = getattr(item.product, field)
                                if field_value:
                                    price = decimal.Decimal(str(field_value))
                                    break
                
                # If still no price, use a proportional calculation from order total
                if price == 0 and item.order and item.order.total:
                    # Distribute order total proportionally by quantity
                    total_items_in_order = OrderItem.objects.filter(order=item.order).aggregate(
                        total_quantity=Sum('quantity')
                    )['total_quantity'] or 1
                    
                    if total_items_in_order > 0:
                        price = item.order.total / total_items_in_order
                
                item_revenue = item.quantity * price
                category_revenue[category_name] += item_revenue
                
                print(f"Item: {item.product.name if item.product else 'No product'}, "
                      f"Category: {category_name}, "
                      f"Qty: {item.quantity}, Price: {price}, Revenue: {item_revenue}")
        
        # Convert to list of category objects with total_revenue
        result = []
        for category_name, revenue in sorted(category_revenue.items(), key=lambda x: x[1], reverse=True):
            # Create a mock category-like object
            class MockCategory:
                def __init__(self, name, total_revenue):
                    self.name = name
                    self.total_revenue = total_revenue
            
            result.append(MockCategory(category_name, revenue))
            print(f"Category {category_name}: ${revenue}")
        
        return result






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
    

    