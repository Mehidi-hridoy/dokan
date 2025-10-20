from django.urls import path
from . import views

app_name = 'orders'
urlpatterns = [
    path('cart/add/<slug:slug>/', views.add_to_cart, name='add_to_cart'),
    path('cart-view/', views.view_cart, name='view_cart'),
    path('cart/update/', views.update_cart, name='update_cart'),
    path('cart/remove/', views.remove_from_cart, name='remove_from_cart'),  # Updated to POST-based
    path('cart/remove-ajax/', views.remove_from_cart_ajax, name='remove_from_cart_ajax'),
    path('cart/dropdown-content/', views.cart_dropdown_content, name='cart_dropdown_content'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout-from-product/<slug:product_slug>/', views.checkout_from_product, name='checkout_from_product'),
    path('thank-you/<int:order_id>/', views.thank_you, name='thank_you'),
    path('<int:order_id>/', views.order_detail, name='order_detail'),  # NEW: order detail
    path('add-review/', views.add_review, name='add_review'),  # ADD THIS


    path('order/history/', views.order_history, name='order_history'),
]