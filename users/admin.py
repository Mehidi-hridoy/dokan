from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'user_type', 'is_staff', 'is_superuser')
    list_filter = ('user_type', 'is_staff', 'is_superuser')

    # ✅ 1. Allow staff to edit/add, but not delete
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete
        return request.user.is_superuser

    def has_add_permission(self, request):
        # Staff and superusers can add
        return request.user.is_staff or request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        # Prevent staff from editing superuser accounts
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return request.user.is_staff or request.user.is_superuser

    # ✅ 2. Remove the bulk delete action for non-superusers
    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            if 'delete_selected' in actions:
                del actions['delete_selected']
        return actions

    # ✅ 3. (Optional) Hide “Delete” button in the change form for staff
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj and obj.is_superuser and not request.user.is_superuser:
            # Prevent staff from editing superuser fields
            return [f.name for f in self.model._meta.fields]
        return readonly_fields
