import secrets

from boarding.models import BoardingPass
from boarding.utils import AIRPORT_TIME_ZONE, get_check_in_window
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from .models import Airline, Booking, Flight


def flight_list(request):
    """Show upcoming scheduled flights with optional airline and date filters."""
    if request.user.is_authenticated and request.user.is_staff and not request.user.is_superuser:
        messages.info(request, "Gate staff accounts are directed to the gate scanner and departures board.")
        return redirect("gate_scanner")

    selected_airline = request.GET.get("airline", "").strip()
    selected_date = request.GET.get("date", "").strip()

    flights = Flight.objects.filter(
        departure_date__gte=timezone.localdate(),
    ).select_related("airline")

    for flight in flights:
        flight.sync_status()

    flights = flights.filter(status__in=["scheduled", "boarding"])

    if selected_airline:
        if selected_airline.isdigit():
            flights = flights.filter(airline_id=int(selected_airline))
        else:
            flights = flights.none()

    if selected_date:
        parsed_date = parse_date(selected_date)
        if parsed_date:
            flights = flights.filter(departure_date=parsed_date)
        else:
            flights = flights.none()

    flights = flights.order_by("departure_date", "departure_time", "flight_number")
    return render(
        request,
        "flights/flight_list.html",
        {
            "flights": flights,
            "airlines": Airline.objects.order_by("name"),
            "selected_airline": selected_airline,
            "selected_date": selected_date,
        },
    )


def _flight_is_bookable(flight):
    """Return whether a flight is scheduled, upcoming, and has seats left."""
    flight.sync_status()
    return (
        flight.status in ("scheduled", "boarding")
        and flight.departure_date >= timezone.localdate()
        and flight.available_seats > 0
    )


def _available_seat_numbers(flight):
    """List free seats using a simple six-seat row layout."""
    occupied = set(
        Booking.objects.filter(flight=flight, booking_status="confirmed")
        .values_list("seat_number", flat=True)
    )
    columns = "ABCDEF"
    seats = []
    for seat_index in range(flight.total_seats):
        row = seat_index // len(columns) + 1
        column = columns[seat_index % len(columns)]
        seat_number = f"{row}{column}"
        if seat_number not in occupied:
            seats.append(seat_number)
    return seats[:flight.available_seats]


def _new_booking_reference():
    """Create a unique DKA-YYYY-NNNNN booking reference."""
    while True:
        sequence = secrets.randbelow(100000)
        reference = f"DKA-{timezone.localdate().year}-{sequence:05d}"
        if not Booking.objects.filter(booking_reference=reference).exists():
            return reference


def _booking_can_be_cancelled(booking):
    """Only confirmed, not-yet-checked-in bookings before flight departure can be cancelled."""
    checked_in = BoardingPass.objects.filter(
        booking=booking,
        is_checked_in=True,
    ).exists()
    return (
        booking.booking_status == "confirmed"
        and not checked_in
        and booking.flight.status != "departed"
    )


@login_required
def book_flight(request, flight_id):
    """Show flight and seat choices, then book the selected seat on POST."""
    if request.user.is_staff and not request.user.is_superuser:
        messages.warning(request, "Gate staff accounts cannot book passenger tickets. Please use a passenger account.")
        return redirect("gate_scanner")

    if request.method != "POST":
        flight = get_object_or_404(
            Flight.objects.select_related("airline"),
            pk=flight_id,
        )
        if Booking.objects.filter(
            passenger=request.user,
            flight=flight,
            booking_status="confirmed",
        ).exists():
            messages.info(request, "You already booked this flight. You can review it in My bookings.")
            return redirect("my_bookings")

        seat_options = _available_seat_numbers(flight)
        if not _flight_is_bookable(flight) or not seat_options:
            messages.error(request, "This flight is no longer available to book.")
            return redirect("flight_list")
        return render(
            request,
            "flights/booking_confirm.html",
            {"flight": flight, "seat_options": seat_options},
        )

    requested_seat = request.POST.get("seat_number", "").strip().upper()
    failure_message = None
    retry_confirmation = False
    booking = None
    with transaction.atomic():
        flight = get_object_or_404(
            Flight.objects.select_for_update().select_related("airline"),
            pk=flight_id,
        )
        already_booked = Booking.objects.filter(
            passenger=request.user,
            flight=flight,
            booking_status="confirmed",
        ).exists()
        if already_booked:
            failure_message = "You already have a confirmed booking for this flight."
        elif not _flight_is_bookable(flight):
            failure_message = "This flight is no longer available to book."
        else:
            seat_options = _available_seat_numbers(flight)
            if not seat_options:
                failure_message = "No seats remain on this flight."
            elif requested_seat not in seat_options:
                failure_message = "That seat is no longer available. Please choose another seat."
                retry_confirmation = True
            else:
                booking = Booking.objects.create(
                    passenger=request.user,
                    flight=flight,
                    booking_reference=_new_booking_reference(),
                    seat_number=requested_seat,
                )
                flight.available_seats -= 1
                flight.save(update_fields=["available_seats"])

    if failure_message:
        messages.error(request, failure_message)
        if retry_confirmation:
            return redirect("book_flight", flight_id=flight_id)
        return redirect("flight_list")

    return redirect("booking_confirmation", booking_id=booking.id)


@login_required
def booking_confirmation(request, booking_id):
    """Show the signed-in passenger the confirmation and reference for their booking."""
    booking = get_object_or_404(
        Booking.objects.select_related("flight__airline"),
        pk=booking_id,
        passenger=request.user,
    )
    window = get_check_in_window(booking.flight)
    return render(
        request,
        "flights/booking_success.html",
        {
            "booking": booking,
            "can_check_in": window["state"] == "open",
            "check_in_state": window["state"],
            "check_in_opens_at": window["opens_at"],
            "check_in_closes_at": window["closes_at"],
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def cancel_booking(request, booking_id):
    """Confirm cancellation and return a seat only when cancellation is still allowed."""
    if request.method == "GET":
        booking = get_object_or_404(
            Booking.objects.select_related("flight__airline"),
            pk=booking_id,
            passenger=request.user,
        )
        if not _booking_can_be_cancelled(booking):
            messages.error(request, "This booking can no longer be cancelled.")
            return redirect("my_bookings")
        return render(request, "flights/cancel_booking.html", {"booking": booking})

    with transaction.atomic():
        booking = get_object_or_404(
            Booking.objects.select_for_update().select_related("flight__airline"),
            pk=booking_id,
            passenger=request.user,
        )
        flight = Flight.objects.select_for_update().get(pk=booking.flight_id)
        booking.flight = flight

        if not _booking_can_be_cancelled(booking):
            messages.error(request, "This booking can no longer be cancelled.")
            return redirect("my_bookings")

        booking.booking_status = "cancelled"
        booking.save(update_fields=["booking_status"])
        flight.available_seats = min(flight.total_seats, flight.available_seats + 1)
        flight.save(update_fields=["available_seats"])

    messages.success(request, f"Booking {booking.booking_reference} has been cancelled and the seat released.")
    return redirect("my_bookings")


@login_required
def my_bookings(request):
    """Show the passenger's bookings with check-in and cancellation states."""
    now = timezone.now()
    bookings = list(
        Booking.objects.filter(passenger=request.user)
        .select_related("flight", "flight__airline", "boarding_pass")
        .order_by("-booking_date")
    )

    for booking in bookings:
        try:
            boarding_pass = booking.boarding_pass
        except BoardingPass.DoesNotExist:
            boarding_pass = None

        booking.passenger_boarding_pass = boarding_pass
        booking.booking_date_wat = timezone.localtime(booking.booking_date, AIRPORT_TIME_ZONE)
        booking.show_check_in = False
        booking.flight.sync_status()

        window = get_check_in_window(booking.flight, now=now)
        booking.check_in_state = window["state"]
        booking.check_in_opens_at = window["opens_at"]
        booking.check_in_closes_at = window["closes_at"]

        if booking.booking_status == "cancelled":
            booking.display_status = "Cancelled"
            booking.status_style = "danger"
        elif boarding_pass and boarding_pass.is_checked_in:
            booking.display_status = "Checked in · View boarding pass"
            booking.status_style = "info"
        elif booking.flight.status == "cancelled":
            booking.display_status = "Flight cancelled"
            booking.status_style = "danger"
        else:
            if window["state"] in ("closed", "unavailable"):
                booking.display_status = "Confirmed · Check-in closed"
                booking.status_style = "warning"
            elif window["state"] == "not_yet_open":
                booking.display_status = "Confirmed · Check-in not yet open"
                booking.status_style = "warning"
            else:
                booking.display_status = "Confirmed · Check-in available"
                booking.status_style = "success"
                booking.show_check_in = True

        booking.can_cancel = (
            booking.booking_status == "confirmed"
            and not (boarding_pass and boarding_pass.is_checked_in)
            and booking.flight.status != "departed"
        )

    return render(request, "flights/my_bookings.html", {"bookings": bookings})
