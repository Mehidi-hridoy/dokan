from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('products.urls', namespace='products')),
    path('users/', include('users.urls', namespace='users')),
    path('orders/', include('orders.urls', namespace='orders')),
    path('ckeditor5/', include('django_ckeditor_5.urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    

# Custom Admin Site Configuration
admin.site.site_header = "Dokan Ecommer Administration"
admin.site.site_title = "Dokan Ecommer Admin Portal"
admin.site.index_title = "Welcome to Dokan Ecommer Admin"