# analytics/urls.py
from django.urls import path
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from . import views

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', staff_member_required(views.AnalyticsDashboard.as_view()), name='dashboard'),
    path('sales/', staff_member_required(views.SalesAnalyticsView.as_view()), name='sales'),
    path('orders/', staff_member_required(views.OrdersAnalyticsView.as_view()), name='orders'),
    path('inventory/', staff_member_required(views.InventoryAnalyticsView.as_view()), name='inventory'),
    path('products/', staff_member_required(views.ProductsAnalyticsView.as_view()), name='products'),
    path('revenue/', staff_member_required(views.RevenueAnalyticsView.as_view()), name='revenue'),
    path('customers/', staff_member_required(views.CustomerListView.as_view()), name='customer_list'),
    path('customers/detail/<int:pk>/', staff_member_required(views.CustomerDetailView.as_view()), name='customer_detail'),
]