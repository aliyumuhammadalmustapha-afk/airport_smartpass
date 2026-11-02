from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.dashboard, name="admin_panel"),
    path("flights/", admin_views.flights_list, name="admin_panel_flights"),
    path("flights/add/", admin_views.flight_add, name="admin_panel_flight_add"),
    path("flights/<int:flight_id>/edit/", admin_views.flight_edit, name="admin_panel_flight_edit"),
    path("flights/<int:flight_id>/cancel/", admin_views.flight_cancel, name="admin_panel_flight_cancel"),
    path("flights/<int:flight_id>/delete/", admin_views.flight_delete, name="admin_panel_flight_delete"),
    path("airlines/", admin_views.airlines_list, name="admin_panel_airlines"),
    path("airlines/add/", admin_views.airline_add, name="admin_panel_airline_add"),
    path("airlines/<int:airline_id>/edit/", admin_views.airline_edit, name="admin_panel_airline_edit"),
    path("airlines/<int:airline_id>/delete/", admin_views.airline_delete, name="admin_panel_airline_delete"),
    path("staff/", admin_views.staff_list, name="admin_panel_staff"),
    path("staff/add/", admin_views.staff_add, name="admin_panel_staff_add"),
    path("staff/<int:staff_id>/edit/", admin_views.staff_edit, name="admin_panel_staff_edit"),
    path("staff/<int:staff_id>/toggle-active/", admin_views.staff_toggle_active, name="admin_panel_staff_toggle_active"),
    path("staff/<int:staff_id>/delete/", admin_views.staff_delete, name="admin_panel_staff_delete"),
    path("bookings/", admin_views.bookings_list, name="admin_panel_bookings"),
    path("bookings/<int:booking_id>/cancel/", admin_views.booking_cancel, name="admin_panel_booking_cancel"),
    path("passes/", admin_views.passes_list, name="admin_panel_passes"),
    path("logs/", admin_views.logs_list, name="admin_panel_logs"),
]
