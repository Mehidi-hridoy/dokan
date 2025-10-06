from django.core.management.base import BaseCommand
from products.models import Category, Brand, Product, Inventory, Attribute, AttributeValue
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Create sample products for testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample products...')
        
        # Create categories
        electronics, _ = Category.objects.get_or_create(
            name='Electronics',
            slug='electronics',
            defaults={'description': 'Latest electronic gadgets and devices'}
        )
        
        clothing, _ = Category.objects.get_or_create(
            name='Clothing',
            slug='clothing', 
            defaults={'description': 'Fashionable clothing for everyone'}
        )
        
        # Create brands
        techcorp, _ = Brand.objects.get_or_create(
            name='TechCorp',
            slug='techcorp',
            defaults={'description': 'Leading technology brand'}
        )
        
        fashionhub, _ = Brand.objects.get_or_create(
            name='FashionHub',
            slug='fashionhub',
            defaults={'description': 'Trendy fashion brand'}
        )
        
        # Create sample products
        sample_products = [
            {
                'name': 'Smartphone X Pro',
                'slug': 'smartphone-x-pro',
                'description': 'Latest flagship smartphone with advanced camera and 5G connectivity',
                'short_description': 'Premium smartphone with exceptional performance',
                'sku': 'SPX-PRO-001',
                'price': 999.99,
                'compare_price': 1199.99,
                'category': electronics,
                'brand': techcorp,
                'status': 'published',
                'featured': True,
            },
            {
                'name': 'Wireless Bluetooth Headphones',
                'slug': 'wireless-bluetooth-headphones',
                'description': 'High-quality wireless headphones with noise cancellation and long battery life',
                'short_description': 'Immersive audio experience',
                'sku': 'WBH-002',
                'price': 199.99,
                'category': electronics,
                'brand': techcorp,
                'status': 'published',
                'featured': True,
            },
            {
                'name': 'Casual T-Shirt',
                'slug': 'casual-t-shirt',
                'description': 'Comfortable and stylish cotton t-shirt for everyday wear',
                'short_description': 'Soft and comfortable cotton t-shirt',
                'sku': 'CTS-003',
                'price': 24.99,
                'compare_price': 29.99,
                'category': clothing,
                'brand': fashionhub,
                'status': 'published',
                'featured': False,
            },
            {
                'name': 'Laptop Ultra',
                'slug': 'laptop-ultra',
                'description': 'High-performance laptop for work and gaming with latest processor',
                'short_description': 'Powerful laptop for all your needs',
                'sku': 'LU-004',
                'price': 1299.99,
                'category': electronics,
                'brand': techcorp,
                'status': 'published',
                'featured': True,
            },
        ]
        
        for product_data in sample_products:
            product, created = Product.objects.get_or_create(
                sku=product_data['sku'],
                defaults=product_data
            )
            if created:
                # Create inventory
                Inventory.objects.create(
                    product=product,
                    quantity=50,
                    low_stock_threshold=10,
                    reorder_level=5
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Created product: {product.name}')
                )
        
        # Create sample attributes
        color_attr, _ = Attribute.objects.get_or_create(
            name='Color',
            slug='color',
            type='color'
        )
        
        size_attr, _ = Attribute.objects.get_or_create(
            name='Size',
            slug='size',
            type='select'
        )
        
        # Create attribute values
        colors = ['Black', 'White', 'Blue', 'Red']
        for color in colors:
            AttributeValue.objects.get_or_create(
                attribute=color_attr,
                value=color
            )
        
        sizes = ['S', 'M', 'L', 'XL']
        for size in sizes:
            AttributeValue.objects.get_or_create(
                attribute=size_attr,
                value=size
            )
        
        self.stdout.write(
            self.style.SUCCESS('Successfully created sample products and attributes!')
        )