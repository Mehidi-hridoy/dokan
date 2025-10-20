from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.home, name='home'),
    path('products-list/', views.ProductListView.as_view(), name='product_list'),
    path('product/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('category/<slug:category_slug>/', views.category_filter, name='category_filter'),
    path('product/<int:product_id>/review/', views.submit_review, name='submit_review'),
    path('search/', views.search, name='search'),
    path('search-suggestions/', views.search_suggestions, name='search_suggestions'),
    path('add-review/', views.add_review, name='add_review'),
]

# ✅ Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
