from django.core.management.base import BaseCommand
from store.models import Category, Brand
from users.models import User
from products.models import Product
import random

class Command(BaseCommand):
    help = "Create 50 demo products"

    def handle(self, *args, **options):
        # Make sure you have at least one category, brand, and user
        category = Category.objects.first()
        brand = Brand.objects.first()
        user = User.objects.first()

        if not category or not brand or not user:
            self.stdout.write(self.style.ERROR("You must have at least one Category, Brand, and User"))
            return

        colors = ['Red', 'Blue', 'Pink', 'Orange', 'Yellow', 'Green', 'Brown']
        sizes = ['S', 'M', 'L', 'XL', 'XXL']
        weights = ['500gm', '1kg', '2kg', '5kg']

        for i in range(1, 51):
            product_name = f"Demo Product {i}"
            base_price = random.randint(100, 1000)
            cost_price = base_price - random.randint(10, 50)
            sale_price = base_price + random.randint(0, 50)

            product = Product.objects.create(
                products_name=product_name,
                category=category,
                brand=brand,
                user=user,
                base_price=base_price,
                cost_price=cost_price,
                sale_price=sale_price,
                color=random.choice(colors),
                size=random.choice(sizes),
                weight=random.choice(weights),
                is_active=True
            )
            product.save()

        self.stdout.write(self.style.SUCCESS("Successfully created 50 demo products"))
