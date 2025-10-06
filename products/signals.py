from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Product, Inventory, ProductVariant, VariantInventory

@receiver(post_save, sender=Product)
def create_product_inventory(sender, instance, created, **kwargs):
    """Automatically create inventory when a product is created"""
    if created and instance.track_inventory:
        Inventory.objects.get_or_create(product=instance)

@receiver(post_save, sender=ProductVariant)
def create_variant_inventory(sender, instance, created, **kwargs):
    """Automatically create inventory when a variant is created"""
    if created:
        VariantInventory.objects.get_or_create(variant=instance)

@receiver(post_save, sender=Product)
def update_product_search_index(sender, instance, **kwargs):
    """Update search index when product is saved"""
    # This would integrate with your search backend (Elasticsearch, etc.)
    pass