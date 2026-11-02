from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import CustomUser
from boarding.models import BoardingPass
from boarding.utils import AIRPORT_TIME_ZONE
from flights.models import Airline, Booking, Flight

from .admin_forms import (
    AirlineAdminForm,
    FlightAdminForm,
    GateStaffCreateForm,
    GateStaffEditForm,
)
from .models import VerificationLog


def admin_required(view):
    """Restrict custom administration pages to authenticated superusers."""
    return user_passes_test(
        lambda user: user.is_superuser,
        login_url="login",
    )(view)


def _admin_form_page(request, form, title, subtitle, cancel_url, success_url, success_message):
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, success_message)
        return redirect(success_url)
    return render(
        request,
        "admin_panel/form.html",
        {
            "form": form,
            "title": title,
            "subtitle": subtitle,
            "cancel_url": cancel_url,
        },
    )


@admin_required
def dashboard(request):
    today = timezone.localtime(timezone.now(), AIRPORT_TIME_ZONE)
    month_start_date = today.date().replace(day=1)
    next_month_date = (month_start_date + timedelta(days=32)).replace(day=1)
    month_start = datetime.combine(month_start_date, datetime.min.time()).replace(tzinfo=AIRPORT_TIME_ZONE)
    month_end = datetime.combine(next_month_date, datetime.min.time()).replace(tzinfo=AIRPORT_TIME_ZONE)
    day_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    scans_today = VerificationLog.objects.filter(scanned_at__gte=day_start, scanned_at__lt=day_end)
    recent_bookings = Booking.objects.select_related("passenger", "flight").order_by("-booking_date")[:6]
    recent_scans = VerificationLog.objects.select_related("scanned_by", "boarding_pass").order_by("-scanned_at")[:6]
    activity = [
        {
            "at": timezone.localtime(booking.booking_date, AIRPORT_TIME_ZONE),
            "title": f"Booking {booking.booking_reference}",
            "detail": f"{booking.passenger.get_full_name() or booking.passenger.email} · {booking.flight.flight_number}",
            "kind": "Booking",
        }
        for booking in recent_bookings
    ]
    activity.extend(
        {
            "at": timezone.localtime(log.scanned_at, AIRPORT_TIME_ZONE),
            "title": f"Gate scan: {log.result.replace('_', ' ')}",
            "detail": f"{log.scanned_by.get_full_name() or log.scanned_by.email if log.scanned_by else 'Unknown staff'} · {log.boarding_pass.flight_number if log.boarding_pass else 'No matched pass'}",
            "kind": "Scan",
        }
        for log in recent_scans
    )
    activity.sort(key=lambda item: item["at"], reverse=True)
    return render(
        request,
        "admin_panel/dashboard.html",
        {
            "today": today,
            "greeting": "morning" if today.hour < 12 else "afternoon" if today.hour < 17 else "evening",
            "flights_today": Flight.objects.filter(
                departure_date=today.date(), status__in=("scheduled", "boarding")
            ).count(),
            "bookings_this_month": Booking.objects.filter(booking_date__gte=month_start, booking_date__lt=month_end).count(),
            "passes_issued": BoardingPass.objects.count(),
            "valid_scans_today": scans_today.filter(result="VALID").count(),
            "used_scans_today": scans_today.filter(result="ALREADY_USED").count(),
            "invalid_scans_today": scans_today.filter(result="INVALID").count(),
            "expired_scans_today": scans_today.filter(result="EXPIRED").count(),
            "recent_bookings": recent_bookings,
            "activity": activity[:10],
        },
    )


@admin_required
def flights_list(request):
    query = request.GET.get("q", "").strip()
    flights = Flight.objects.select_related("airline").order_by("-departure_date", "departure_time")
    for flight in flights:
        flight.sync_status()
    if query:
        flights = flights.filter(
            Q(flight_number__icontains=query)
            | Q(airline__name__icontains=query)
            | Q(destination__icontains=query)
        )
    return render(request, "admin_panel/list.html", {
        "title": "Flights", "subtitle": "Create and update airport flight schedules.",
        "list_type": "flights", "rows": flights, "query": query,
        "add_url": "admin_panel_flight_add", "add_label": "Flight",
    })


@admin_required
@require_http_methods(["GET", "POST"])
def flight_add(request):
    form = FlightAdminForm(request.POST or None)
    return _admin_form_page(request, form, "Add Flight", "Enter the airline, route, schedule, and aircraft capacity.", "admin_panel_flights", "admin_panel_flights", "Flight added successfully.")


@admin_required
@require_http_methods(["GET", "POST"])
def flight_edit(request, flight_id):
    flight = get_object_or_404(Flight, pk=flight_id)
    form = FlightAdminForm(request.POST or None, instance=flight)
    return _admin_form_page(request, form, "Edit Flight", f"Update the schedule for {flight.flight_number}.", "admin_panel_flights", "admin_panel_flights", "Flight updated successfully.")


@admin_required
@require_http_methods(["GET", "POST"])
def flight_cancel(request, flight_id):
    flight = get_object_or_404(Flight, pk=flight_id)
    if request.method == "POST":
        if flight.status == "departed":
            messages.error(request, "A departed flight cannot be cancelled from this panel.")
        elif flight.status != "cancelled":
            flight.status = "cancelled"
            flight.save(update_fields=["status"])
            messages.success(request, f"Flight {flight.flight_number} has been cancelled.")
        return redirect("admin_panel_flights")
    return render(request, "admin_panel/confirm_action.html", {
        "title": "Cancel Flight", "object_label": flight.flight_number,
        "description": "Passengers will no longer be able to book this flight.",
        "cancel_url": "admin_panel_flights",
    })


@admin_required
@require_http_methods(["GET", "POST"])
def flight_delete(request, flight_id):
    flight = get_object_or_404(Flight, pk=flight_id)
    bookings_count = flight.bookings.count()
    if request.method == "POST":
        flight_number = flight.flight_number
        flight.delete()
        messages.success(request, f"Flight {flight_number} and associated records have been permanently deleted.")
        return redirect("admin_panel_flights")
    return render(request, "admin_panel/confirm_action.html", {
        "title": "Delete Flight",
        "object_label": flight.flight_number,
        "description": f"Are you sure you want to permanently delete flight {flight.flight_number}? This flight currently has {bookings_count} associated booking(s).",
        "cancel_url": "admin_panel_flights",
    })


@admin_required
def airlines_list(request):
    query = request.GET.get("q", "").strip()
    airlines = Airline.objects.annotate(flight_count=Count("flights")).order_by("name")
    if query:
        airlines = airlines.filter(Q(name__icontains=query) | Q(code__icontains=query))
    return render(request, "admin_panel/list.html", {
        "title": "Airlines", "subtitle": "Manage airlines operating from DKA.",
        "list_type": "airlines", "rows": airlines, "query": query, "add_url": "admin_panel_airline_add", "add_label": "Airline",
    })


@admin_required
@require_http_methods(["GET", "POST"])
def airline_add(request):
    form = AirlineAdminForm(request.POST or None)
    return _admin_form_page(request, form, "Add Airline", "Add an airline and its unique airport code.", "admin_panel_airlines", "admin_panel_airlines", "Airline added successfully.")


@admin_required
@require_http_methods(["GET", "POST"])
def airline_edit(request, airline_id):
    airline = get_object_or_404(Airline, pk=airline_id)
    form = AirlineAdminForm(request.POST or None, instance=airline)
    return _admin_form_page(request, form, "Edit Airline", f"Update the details for {airline.name}.", "admin_panel_airlines", "admin_panel_airlines", "Airline updated successfully.")


@admin_required
@require_http_methods(["GET", "POST"])
def airline_delete(request, airline_id):
    airline = get_object_or_404(Airline, pk=airline_id)
    flights_count = airline.flights.count()
    if request.method == "POST":
        name = airline.name
        airline.delete()
        messages.success(request, f"Airline {name} has been permanently deleted.")
        return redirect("admin_panel_airlines")
    return render(request, "admin_panel/confirm_action.html", {
        "title": "Delete Airline",
        "object_label": f"{airline.name} ({airline.code})",
        "description": f"Are you sure you want to permanently delete {airline.name}? This will also delete its {flights_count} scheduled flight(s).",
        "cancel_url": "admin_panel_airlines",
    })


@admin_required
def staff_list(request):
    query = request.GET.get("q", "").strip()
    staff = CustomUser.objects.filter(is_staff=True, is_superuser=False).order_by("first_name", "last_name", "email")
    if query:
        staff = staff.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    return render(request, "admin_panel/list.html", {
        "title": "Gate Staff", "subtitle": "Manage accounts allowed to use the gate scanner.",
        "list_type": "staff", "rows": staff, "query": query,
        "add_url": "admin_panel_staff_add", "add_label": "Gate Staff",
    })


@admin_required
@require_http_methods(["GET", "POST"])
def staff_add(request):
    form = GateStaffCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        staff_member = form.save()
        messages.success(request, f"Gate staff account created for {staff_member.email}.")
        return redirect("admin_panel_staff")
    return render(request, "admin_panel/form.html", {
        "form": form, "title": "Add Gate Staff", "subtitle": "Create an active staff account with a secure password.",
        "cancel_url": "admin_panel_staff", "password_form": True,
    })


@admin_required
@require_http_methods(["GET", "POST"])
def staff_edit(request, staff_id):
    staff_member = get_object_or_404(CustomUser, pk=staff_id, is_staff=True, is_superuser=False)
    form = GateStaffEditForm(request.POST or None, instance=staff_member)
    return _admin_form_page(request, form, "Edit Gate Staff", f"Update the account for {staff_member.email}.", "admin_panel_staff", "admin_panel_staff", "Staff account updated successfully.")


@admin_required
@require_POST
def staff_toggle_active(request, staff_id):
    staff_member = get_object_or_404(CustomUser, pk=staff_id, is_staff=True, is_superuser=False)
    staff_member.is_active = not staff_member.is_active
    staff_member.save(update_fields=["is_active"])
    state = "activated" if staff_member.is_active else "deactivated"
    messages.success(request, f"{staff_member.email} has been {state}.")
    return redirect("admin_panel_staff")


@admin_required
@require_http_methods(["GET", "POST"])
def staff_delete(request, staff_id):
    staff_member = get_object_or_404(CustomUser, pk=staff_id, is_staff=True, is_superuser=False)
    if request.method == "POST":
        email = staff_member.email
        staff_member.delete()
        messages.success(request, f"Gate staff account {email} has been deleted.")
        return redirect("admin_panel_staff")
    return render(request, "admin_panel/confirm_action.html", {
        "title": "Delete Gate Staff",
        "object_label": staff_member.get_full_name() or staff_member.email,
        "description": f"Are you sure you want to permanently delete gate staff account {staff_member.email}?",
        "cancel_url": "admin_panel_staff",
    })


@admin_required
def bookings_list(request):
    query = request.GET.get("q", "").strip()
    bookings = Booking.objects.select_related("passenger", "flight", "flight__airline").order_by("-booking_date")
    if query:
        bookings = bookings.filter(
            Q(booking_reference__icontains=query)
            | Q(passenger__email__icontains=query)
            | Q(passenger__first_name__icontains=query)
            | Q(passenger__last_name__icontains=query)
            | Q(flight__flight_number__icontains=query)
        )
    return render(request, "admin_panel/list.html", {
        "title": "Bookings", "subtitle": "Search and review passenger bookings.",
        "list_type": "bookings", "rows": bookings, "query": query,
    })


@admin_required
@require_http_methods(["GET", "POST"])
def booking_cancel(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related("passenger", "flight"), pk=booking_id)
    if request.method == "POST":
        with transaction.atomic():
            booking = Booking.objects.select_for_update().select_related("flight").get(pk=booking_id)
            flight = Flight.objects.select_for_update().get(pk=booking.flight_id)
            if booking.booking_status != "cancelled":
                booking.booking_status = "cancelled"
                booking.save(update_fields=["booking_status"])
                flight.available_seats = min(flight.total_seats, flight.available_seats + 1)
                flight.save(update_fields=["available_seats"])
                messages.success(request, f"Booking {booking.booking_reference} cancelled. The seat was released.")
            else:
                messages.info(request, "This booking was already cancelled.")
        return redirect("admin_panel_bookings")
    return render(request, "admin_panel/confirm_action.html", {
        "title": "Cancel Booking", "object_label": booking.booking_reference,
        "description": "This booking will be cancelled and its seat returned to the flight inventory.",
        "cancel_url": "admin_panel_bookings",
    })


@admin_required
def passes_list(request):
    passes = BoardingPass.objects.select_related("booking__passenger", "booking__flight").order_by("-checked_in_at")
    return render(request, "admin_panel/list.html", {
        "title": "Boarding Passes", "subtitle": "Review passes issued after passenger check-in.",
        "list_type": "passes", "rows": passes,
    })


@admin_required
def logs_list(request):
    result = request.GET.get("result", "").strip()
    staff_id = request.GET.get("staff", "").strip()
    scan_date = request.GET.get("date", "").strip()
    logs = VerificationLog.objects.select_related(
        "scanned_by", "boarding_pass", "boarding_pass__booking__flight"
    )
    valid_results = {choice[0] for choice in VerificationLog.RESULT_CHOICES}
    if result in valid_results:
        logs = logs.filter(result=result)
    if staff_id.isdigit():
        logs = logs.filter(scanned_by_id=int(staff_id))
    parsed_date = parse_date(scan_date) if scan_date else None
    if parsed_date:
        date_start = datetime.combine(parsed_date, datetime.min.time()).replace(tzinfo=AIRPORT_TIME_ZONE)
        date_end = date_start + timedelta(days=1)
        logs = logs.filter(scanned_at__gte=date_start, scanned_at__lt=date_end)
    return render(request, "admin_panel/list.html", {
        "title": "Verification Logs", "subtitle": "Audit gate scans by result, staff member, or date.",
        "list_type": "logs", "rows": logs,
        "result_filter": result, "staff_filter": staff_id, "date_filter": scan_date,
        "staff_options": CustomUser.objects.filter(is_staff=True, is_superuser=False).order_by("email"),
        "result_choices": VerificationLog.RESULT_CHOICES,
    })
