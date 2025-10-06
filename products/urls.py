from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # Product listings
    path('', views.product_list, name='product_list'),
    path('search/', views.product_search, name='product_search'),
    path('category/<slug:slug>/', views.category_products, name='category_products'),
    path('brand/<slug:slug>/', views.brand_products, name='brand_products'),
    
    # Product detail
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    
    # Reviews
    path('product/<int:product_id>/review/', views.submit_review, name='submit_review'),
    
    # Wishlist
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # Categories
    path('categories/', views.category_list, name='categories'),
    
    # Brands
    path('brands/', views.brand_list, name='brands'),
]