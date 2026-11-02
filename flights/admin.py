from django.contrib import admin

from .models import Airline, Booking, Flight


@admin.register(Airline)
class AirlineAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = ("flight_number", "airline", "origin", "destination", "departure_date", "departure_time", "available_seats", "status")
    list_filter = ("airline", "status", "departure_date")
    search_fields = ("flight_number", "airline__name", "origin", "destination")
    date_hierarchy = "departure_date"
    list_select_related = ("airline",)
    autocomplete_fields = ("airline",)
    list_editable = ("status",)
    ordering = ("departure_date", "departure_time")
    list_per_page = 25


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("booking_reference", "passenger", "flight", "seat_number", "booking_status", "booking_date")
    list_filter = ("booking_status", "flight__airline", "flight__departure_date")
    search_fields = ("booking_reference", "passenger__email", "passenger__first_name", "passenger__last_name", "flight__flight_number", "seat_number")
    date_hierarchy = "booking_date"
    list_select_related = ("passenger", "flight__airline")
    autocomplete_fields = ("passenger", "flight")
    readonly_fields = ("booking_date",)
    ordering = ("-booking_date",)
    list_per_page = 25
