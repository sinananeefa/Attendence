from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'department', 'is_staff', 'is_active')
    list_filter = ('role', 'department', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Institutional RBAC Profile', {
            'fields': ('role', 'department', 'phone', 'avatar'),
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Institutional RBAC Profile', {
            'fields': ('role', 'department', 'phone', 'avatar'),
        }),
    )
