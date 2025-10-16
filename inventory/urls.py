# inventory/urls.py
from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', login_required(views.InventoryDashboard.as_view()), name='dashboard'),
    path('list/', login_required(views.InventoryListView.as_view()), name='list'),
    path('detail/<int:pk>/', login_required(views.InventoryDetailView.as_view()), name='detail'),
    path('alerts/', login_required(views.StockAlertListView.as_view()), name='alerts'),
    path('restock/<int:pk>/', login_required(views.restock_inventory), name='restock'),
    path('movement/add/<int:inventory_id>/', login_required(views.add_movement), name='add_movement'),
]