from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('products.urls', namespace='products')),
    path('users/', include('users.urls', namespace='users')),
    path('orders/', include('orders.urls', namespace='orders')),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('analytics/', include('analytics.urls', namespace='analytics')),
    path('login/', auth_views.LoginView.as_view( template_name='users/login.html', redirect_authenticated_user=True ), name='login'),
    path('logout/', auth_views.LogoutView.as_view( next_page='products:home' ), name='logout'),
    path('oauth/', include('social_django.urls', namespace='social')),
    path('accounts/', include('allauth.urls')),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    

# Custom Admin Site Configuration
admin.site.site_header = "Dokan Ecommer Administration"
admin.site.site_title = "Dokan Ecommer Admin Portal"
admin.site.index_title = "Welcome to Dokan Ecommer Admin"