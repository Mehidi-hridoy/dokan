from django.db import models

class Inventory(models.Model):
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='inventory_records'
    )
    quantity = models.PositiveIntegerField(default=0)
    location = models.CharField(max_length=100, blank=True, null=True)
    low_stock_threshold = models.PositiveIntegerField(default=5)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"

    @property
    def is_stock_out(self):
        return self.quantity == 0

    @property
    def is_upcoming_stock_out(self):
        return 0 < self.quantity <= self.low_stock_threshold