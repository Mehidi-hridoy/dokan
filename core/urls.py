from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/orders/', views.order_management, name='order_management'),
    path('admin/incomplete-orders/', views.incomplete_orders, name='incomplete_orders'),
    path('admin/pos/', views.pos_management, name='pos_management'),
    path('admin/customers/', views.customer_info, name='customer_info'),
    path('admin/analytics/', views.analytics_dashboard, name='analytics'),
    path('admin/reports/', views.report_generator, name='reports'),
    path('admin/api-settings/', views.api_settings, name='api_settings'),
    path('admin/access-management/', views.access_management, name='access_management'),
]