from django.urls import path
from . import views  # Import your app's views


app_name = 'analytics'

urlpatterns = [
path('', views.order_overview_dashboard, name='analytics_dashboard'), 
]
