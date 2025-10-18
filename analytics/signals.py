from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from orders.models import Order


@receiver(post_save, sender=Order)
def update_customer_on_save(sender, instance, **kwargs):
    if instance.user:
        # If you had a Customer model linked to User, update it here
        # Example: Customer.objects.filter(user=instance.user).update_aggregates()
        pass

@receiver(post_delete, sender=Order)
def update_customer_on_delete(sender, instance, **kwargs):
    if instance.user:
        # Similarly, update Customer aggregates if needed
        pass
