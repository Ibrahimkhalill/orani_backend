from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserProfile, OTP

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser

    list_display = ('phone_number', 'email', 'role', 'is_staff', 'is_active', 'is_verified')

    fieldsets = (
        (None, {'fields': ('phone_number', 'email', 'password')}),
        ('Permissions', {'fields': ('role', 'is_staff', 'is_active', 'is_verified', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
    )

    search_fields = ('phone_number', 'email')
    ordering = ('phone_number',)


admin.site.register(UserProfile)
admin.site.register(OTP)