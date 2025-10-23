# core/admin.py
from django.contrib import admin
from django.conf import settings

# Use your settings or set directly
admin.site.site_header = getattr(settings, 'ADMIN_SITE_HEADER', "Dokan Ecommerce Administration")
admin.site.site_title = getattr(settings, 'ADMIN_SITE_TITLE', "Dokan Admin")
admin.site.index_title = getattr(settings, 'ADMIN_INDEX_TITLE', "Dashboard")  # This fixes it!