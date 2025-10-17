from django.conf import settings
from django.urls import path
from django.conf.urls.static import static
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.home, name='home'),
    path('products-list/', views.ProductListView.as_view(), name='product_list'),
    path('product/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('search/', views.search, name='search'),
    path('search-suggestions/', views.search_suggestions, name='search_suggestions'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
