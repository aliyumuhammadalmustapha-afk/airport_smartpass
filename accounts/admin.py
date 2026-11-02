from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "last_name", "phone_number", "account_role", "is_active")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "username", "first_name", "last_name", "phone_number")
    ordering = ("email",)
    fieldsets = UserAdmin.fieldsets + (("Additional Info", {"fields": ("phone_number",)}),)

    @admin.display(description="Account role")
    def account_role(self, user):
        if user.is_superuser:
            return "Administrator"
        if user.is_staff:
            return "Gate staff"
        return "Passenger"
