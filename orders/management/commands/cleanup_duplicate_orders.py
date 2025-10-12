import random, uuid
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from orders.models import Order, OrderItem
from products.models import Product
from analytics.models import Customer
from django.contrib.auth import get_user_model

User = get_user_model()

user_obj = User.objects.first() or User.objects.create_user(username='demo_user', email='demo@test.com', password='1234')
customer_obj = Customer.objects.first() or Customer.objects.create(name='Demo Customer')
products = list(Product.objects.all())

if not products:
    print("⚠️ No products found! Please create products first.")
else:
    order_statuses = ['pending', 'confirmed', 'processed', 'hold', 'rejected']
    courier_statuses = ['pending', 'in_transit', 'delivered', 'returned']
    payment_statuses = ['pending', 'paid', 'failed']
    payment_methods = ['cod', 'card', 'mobile_money']
    couriers = ['Pathao', 'RedX', 'Steadfast']
    delivery_status_choices = [choice[0] for choice in OrderItem.DELIVERY_STATUS_CHOICES]
    areas = ['Dhaka', 'Chattogram', 'Sylhet', 'Rajshahi']
    cities = ['Gulshan', 'Mirpur', 'Banani', 'Agrabad', 'Zindabazar']

    for i in range(50):
        product = random.choice(products)
        qty = random.randint(1, 5)
        price = product.price
        subtotal = price * qty
        tax = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
        shipping = Decimal(random.randint(40, 120))
        discount = Decimal(random.randint(0, 50))
        total = subtotal + tax + shipping - discount

        order = Order.objects.create(
            user=user_obj,
            customer_name=customer_obj,
            order_number=f"ORD-{uuid.uuid4().hex[:5].upper()}",
            order_status=random.choice(order_statuses),
            courier_status=random.choice(courier_statuses),
            payment_status=random.choice(payment_statuses),
            payment_method=random.choice(payment_methods),
            courier_name=random.choice(couriers),
            courier_choice=random.choice(['pathao', 'red_x', 'steadfast']),
            subtotal=subtotal,
            tax_amount=tax,
            shipping_cost=shipping,
            discount_amount=discount,
            total=total,
            phone_number=f"017{random.randint(10000000,99999999)}",
            email=f"demo{i}@example.com",
            shipping_address=f"House {i}, Road {random.randint(1,50)}, {random.choice(areas)}",
            billing_address=f"Billing Address {i}",
            delivery_area=random.choice(areas),
            city=random.choice(cities),
            zip_code=str(random.randint(1200, 6000)),
            estimated_delivery=timezone.now().date() + timedelta(days=random.randint(1,5)),
            created_at=timezone.now() - timedelta(hours=random.randint(1,24)),
        )

        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=qty,
            price=price,
            delivery_status=random.choice(delivery_status_choices)
        )

        print(f"✅ Created order {order.order_number} | Total: {total} | Status: {order.order_status}")

    print("\n🎉 Done! 50 demo orders successfully created.")
