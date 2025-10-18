"""
python manage.py makemigrations 
python manage.py migrate
python manage.py runserver

git add .
git commit -m "Updated Bav Bar and more "
git push -u origin main
python manage.py runserver

git pull origin main


git remote add origin https://github.com/Mehidi-hridoy/dokan.git

git branch -M main 
git push -u origin main

pip install -r requirements.txt

python manage.py createsuperuser

"""


"""
from orders.models import Order, OrderItem
from products.models import Product
from analytics.models import Customer
from users.models import User
from decimal import Decimal
import random
from datetime import datetime, timedelta
from django.utils import timezone

# Pick a user and a customer
user = User.objects.first()
customer = Customer.objects.first()

# Get 10 products (5 men, 5 women)
products = list(Product.objects.all()[:10])

# Create 5 random orders
for i in range(5):
    order = Order.objects.create(
        user=user,
        customer=customer,
        order_status=random.choice(['confirmed', 'pending', 'processed']),
        payment_status='paid',
        subtotal=0,
        tax_amount=Decimal('50.00'),
        shipping_cost=Decimal('100.00'),
        discount_amount=Decimal('20.00'),
        delivery_area="Dhaka",
        created_at=timezone.now() - timedelta(days=random.randint(1, 30))  # simulate recent orders
    )
    
    # Add 2-3 random products to each order
    order_items = random.sample(products, 2)
    subtotal = 0
    for p in order_items:
        quantity = random.randint(1, 3)
        OrderItem.objects.create(order=order, product=p, quantity=quantity)
        subtotal += p.current_price * quantity

    # Update subtotal and total
    order.subtotal = subtotal
    order.total = subtotal + order.tax_amount + order.shipping_cost - order.discount_amount
    order.save()

print("5 orders with order items created successfully!")

"""