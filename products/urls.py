from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static


app_name = 'products'

urlpatterns = [
    path('', views.home, name='home'),
    path('products-list/', views.product_list, name='product_list'),



] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)