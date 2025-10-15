# analytics/urls.py

from django.urls import path
from . import views 


app_name = 'analytics'

urlpatterns = [
    # Main Dashboard
    path('', views.analytics_dashboard, name='analytics_dashboard'), 
    
    # Customer Management
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:customer_id>/toggle-status/', views.toggle_customer_status, name='toggle_customer_status'),
    path('api/customer-search/', views.customer_search_api, name='customer_search_api'),
    
    # Financial/Sales Analytics Details
    path('sales-analytics/', views.sales_analytics_detail, name='sales_analytics'),
    path('financial-dashboard/', views.financial_dashboard, name='financial_dashboard'), # High-level finance metrics
    path('expense-analytics/', views.expense_analytics_detail, name='expense_analytics'),
    
    # Financial Records / Transaction List (Detailed)
    path('financial/', views.financial_analytics, name='financial_analytics'),
    
    # API for Charts
    path('dashboard-data/', views.dashboard_data_api, name='dashboard_data'),
]