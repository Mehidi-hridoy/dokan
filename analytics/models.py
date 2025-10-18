# analytics/models.py
from django.db import models


class SalesSummary(models.Model):
    date = models.DateField(unique=True)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    completed_orders = models.PositiveIntegerField(default=0)
    pending_orders = models.PositiveIntegerField(default=0)
    processing_orders = models.PositiveIntegerField(default=0)
    canceled_orders = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Sales Summary'
        verbose_name_plural = 'Sales Summaries'

    def __str__(self):
        return f"Sales Summary for {self.date}"

class InventorySummary(models.Model):
    date = models.DateField(unique=True)
    total_stock = models.PositiveIntegerField(default=0)
    in_stock_items = models.PositiveIntegerField(default=0)
    low_stock_items = models.PositiveIntegerField(default=0)  # e.g., quantity < 10
    out_of_stock_items = models.PositiveIntegerField(default=0)
    on_delivery = models.PositiveIntegerField(default=0)  # Items in transit or pending delivery

    class Meta:
        ordering = ['-date']
        verbose_name = 'Inventory Summary'
        verbose_name_plural = 'Inventory Summaries'

    def __str__(self):
        return f"Inventory Summary for {self.date}"

class CustomerSummary(models.Model):
    date = models.DateField(unique=True)
    total_customers = models.PositiveIntegerField(default=0)
    new_customers = models.PositiveIntegerField(default=0)
    repeat_customers = models.PositiveIntegerField(default=0)
    active_customers = models.PositiveIntegerField(default=0)  # e.g., customers with recent activity

    class Meta:
        ordering = ['-date']
        verbose_name = 'Customer Summary'
        verbose_name_plural = 'Customer Summaries'

    def __str__(self):
        return f"Customer Summary for {self.date}"
    