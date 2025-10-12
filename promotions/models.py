from django.db import models
from products.models import Product
from users.models import User
from django.utils import timezone

class Promotion(models.Model):
    PROMO_TYPE_CHOICES = [
        ('percentage', 'Percentage Discount'),
        ('fixed', 'Fixed Amount Discount'),
        ('bogo', 'Buy One Get One'),
        ('free_shipping', 'Free Shipping'),
        ('bundle', 'Bundle Offer'),
    ]

    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="Optional coupon code")
    description = models.TextField(blank=True, null=True)

    promo_type = models.CharField(max_length=50, choices=PROMO_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    products = models.ManyToManyField(Product, blank=True, related_name='promotions')

    usage_limit = models.PositiveIntegerField(blank=True, null=True, help_text="Total times this promo can be used")
    user_limit = models.PositiveIntegerField(blank=True, null=True, help_text="Times a single user can use this promo")

    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_promotions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.promo_type})"

    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date and self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True

    def apply_discount(self, order_total):
        if not self.is_valid() or not self.discount_value:
            return order_total
        if self.promo_type == 'percentage':
            return order_total - (order_total * self.discount_value / 100)
        elif self.promo_type == 'fixed':
            return max(order_total - self.discount_value, 0)
        return order_total


class PromotionUsage(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='promo_usages')
    order_id = models.CharField(max_length=50, blank=True, null=True, help_text="Optional order reference")
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('promotion', 'user', 'order_id')
        ordering = ['-used_at']

    def __str__(self):
        return f"{self.user.username} used {self.promotion.name} at {self.used_at}"

class PromotionCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='codes')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.code} for {self.promotion.name}"

    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date and self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True
