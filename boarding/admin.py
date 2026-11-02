from django.contrib import admin

from .models import BoardingPass


@admin.register(BoardingPass)
class BoardingPassAdmin(admin.ModelAdmin):
    list_display = ("pass_code", "passenger_name", "flight_number", "seat_number", "departure_date", "is_checked_in", "is_used")
    list_filter = ("is_checked_in", "is_used", "departure_date")
    search_fields = ("pass_code", "passenger_name", "flight_number", "seat_number", "booking__booking_reference", "booking__passenger__email")
    date_hierarchy = "departure_date"
    list_select_related = ("booking__passenger", "booking__flight")
    autocomplete_fields = ("booking",)
    readonly_fields = ("pass_code", "checked_in_at", "used_at")
    ordering = ("-departure_date", "flight_number")
    list_per_page = 25
