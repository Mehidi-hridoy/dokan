# analytics/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender='orders.Order')
def update_customer_on_save(sender, instance, **kwargs):
    if instance.customer:
        instance.customer.update_aggregates()

@receiver(post_delete, sender='orders.Order')
def update_customer_on_delete(sender, instance, **kwargs):
    if instance.customer:
        instance.customer.update_aggregates()