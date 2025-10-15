from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add/<slug:slug>/', views.add_to_cart, name='add_to_cart'),  # Updated to use slug
    path('cart/update/', views.update_cart, name='update_cart_guest'),  # For guest users
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/dropdown-content/', views.cart_dropdown_content, name='cart_dropdown_content'),
    path('add-review/', views.add_review, name='add_review'),
    path('orders/history/', views.order_history, name='order_history'),
    path('checkout/', views.checkout, name='checkout'),  
    path('thank-you/<int:order_id>/', views.thank_you, name='thank_you'),  # Add thank_you here
# urls.py
path('cart/session/update/<int:item_index>/', views.session_update_cart, name='session_update_cart'),
path('cart/session/remove/<int:item_index>/', views.session_remove_cart, name='session_remove_cart'),

    
]