"""
python manage.py makemigrations 
python manage.py migrate
python manage.py runserver

git add .
git commit -m "Prepare for Heroku deployment with Postgres"
git push -u origin main
python manage.py runserver


git add .
git commit -m "Prepare for Heroku deployment with Postgres"
git push origin main
python manage.py runserver


git push heroku main


git pull origin main


git add.
git commit -m "Fix ALLOWED_HOSTS for Heroku"
git push heroku main



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

"""
from products.models import Product
from store.models import Category, Brand
from users.models import User
from decimal import Decimal
import uuid
import random
from django.utils.text import slugify

user = User.objects.first()
brand = Brand.objects.first()
category = Category.objects.first()

mens_products = ["Men's Casual Shirt","Men's Formal Shirt","Men's Jeans","Men's T-Shirt","Men's Jacket","Men's Shorts","Men's Sweater","Men's Polo Shirt","Men's Hoodie","Men's Sneakers"]
womens_products = ["Women's Dress","Women's Skirt","Women's Blouse","Women's Jeans","Women's T-Shirt","Women's Jacket","Women's Sweater","Women's Shorts","Women's Sandals","Women's Sneakers"]

all_products = mens_products + womens_products
colors = ['Red','Blue','Pink','Orange','Yellow','Green','Brown']
sizes = ['S','M','L','XL','XXL']
weights = ['500gm','1kg','2kg','5kg']

for name in all_products:
    base_price = Decimal(random.randint(1000,5000))
    sale_price = Decimal(random.randint(800,int(base_price)))
    cost_price = Decimal(random.randint(500,int(base_price*Decimal('0.8'))))
    unique_slug = f"{slugify(name)}-{uuid.uuid4().hex[:6]}"
    product = Product.objects.create(products_name=name, slug=unique_slug, user=user, brand=brand, category=category, base_price=base_price, sale_price=sale_price, cost_price=cost_price, color=random.choice(colors), size=random.choice(sizes), weight=random.choice(weights))
    print(f"Created: {product.products_name} | Base: {base_price} | Sale: {sale_price} | Cost: {cost_price} | Code: {product.product_code} | Slug: {product.slug}")


    
from inventory.models import Inventory
import random

quantities = [5, 10, 20, 50, 100]
low_stock_thresholds = [3, 5, 10]
reorder_quantities = [5, 10, 20]

for inv in Inventory.objects.all():
    inv.quantity = random.choice(quantities)
    inv.low_stock_threshold = random.choice(low_stock_thresholds)
    inv.reorder_quantity = random.choice(reorder_quantities)
    inv.save()



"""