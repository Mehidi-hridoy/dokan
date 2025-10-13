from django.urls import path
from . import views  # Import your app's views


app_name = 'analytics'

urlpatterns = [
path('', views.analytics_dashboard, name='analytics_dashboard'), 
path('customers/', views.customer_analytics, name='customer_analytics'),
path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
path('customers/<int:customer_id>/toggle-status/', views.toggle_customer_status, name='toggle_customer_status'),
path('api/customer-search/', views.customer_search_api, name='customer_search_api'),
#finacial analytics
path('sales-analytics/', views.sales_analytics_detail, name='sales_analytics'),
path('financial-dashboard/', views.financial_dashboard, name='financial_dashboard'),
path('expense-analytics/', views.expense_analytics_detail, name='expense_analytics'),


]
