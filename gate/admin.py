from django.contrib import admin

from .models import VerificationLog


@admin.register(VerificationLog)
class VerificationLogAdmin(admin.ModelAdmin):
    list_display = ("result", "scanned_by", "scanned_at", "boarding_pass", "scanned_code", "notes")
    list_display_links = None
    list_filter = ("result", "scanned_at")
    search_fields = ("scanned_code", "scanned_by__email", "boarding_pass__passenger_name", "boarding_pass__flight_number")
    date_hierarchy = "scanned_at"
    list_select_related = ("scanned_by", "boarding_pass")
    readonly_fields = ("result", "scanned_by", "scanned_at", "boarding_pass", "scanned_code", "notes")
    ordering = ("-scanned_at",)
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.site_header = "DKA Airport Administration"
admin.site.site_title = "DKA Administration"
admin.site.index_title = "Manage airport operations"
