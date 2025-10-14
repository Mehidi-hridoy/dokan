
from django.conf import settings
from django.urls import path
from django.conf.urls.static import static
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('search/', views.search, name='search'),
    path('cart/add/<slug:slug>/', views.add_to_cart, name='add_to_cart'),  # Updated to use slug
    path('cart/', views.view_cart, name='view_cart'),
    path('orders/history/', views.order_history, name='order_history'),
    path('checkout/', views.checkout, name='checkout'),  # Remove @require_POST decorator from view
    path('thank-you/<int:order_id>/', views.thank_you, name='thank_you'),  # Add thank_you here
    path('add-review/', views.add_review, name='add_review'),
    path('search-suggestions/', views.search_suggestions, name='search_suggestions'),
    path('cart/dropdown-content/', views.cart_dropdown_content, name='cart_dropdown_content'),


    

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


