from datetime import datetime, timedelta
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from flights.models import Booking

from .models import BoardingPass
from .qr_codes import generate_qr_code
from .utils import get_check_in_window


def _booking_can_check_in(booking):
    """Allow a confirmed booking only while its WAT check-in window is open."""
    return (
        booking.booking_status == "confirmed"
        and get_check_in_window(booking.flight)["state"] == "open"
    )


def _check_in_unavailable_message(state):
    """Explain why online check-in is unavailable at this time."""
    if state == "not_yet_open":
        return "Online check-in opens 24 hours before departure. Please return during the check-in window."
    if state == "closed":
        return "Online check-in closes 1 hour before departure. This check-in window has closed."
    return "This booking or flight is not eligible for online check-in."


@login_required
def check_in(request, booking_id):
    """Create a boarding pass and its UUID QR image for a passenger booking."""
    if request.method == "POST":
        with transaction.atomic():
            booking = get_object_or_404(
                Booking.objects.select_for_update().select_related("flight__airline", "passenger"),
                pk=booking_id,
                passenger=request.user,
            )
            existing_pass = BoardingPass.objects.filter(booking=booking).first()
            if existing_pass:
                generate_qr_code(existing_pass)
            elif not _booking_can_check_in(booking):
                window = get_check_in_window(booking.flight)
                messages.error(request, _check_in_unavailable_message(window["state"]))
                return redirect("my_bookings")
            else:
                passenger_name = booking.passenger.get_full_name().strip()
                if not passenger_name:
                    passenger_name = booking.passenger.email
                departure = datetime.combine(
                    booking.flight.departure_date,
                    booking.flight.departure_time,
                )
                boarding_time = (departure - timedelta(minutes=30)).time()
                boarding_pass = BoardingPass.objects.create(
                    booking=booking,
                    passenger_name=passenger_name,
                    flight_number=booking.flight.flight_number,
                    origin=booking.flight.origin,
                    destination=booking.flight.destination,
                    departure_date=booking.flight.departure_date,
                    departure_time=booking.flight.departure_time,
                    seat_number=booking.seat_number,
                    boarding_time=boarding_time,
                    airline_name=booking.flight.airline.name,
                    is_checked_in=True,
                    checked_in_at=timezone.now(),
                )
                generate_qr_code(boarding_pass)
        return redirect("check_in", booking_id=booking_id)

    booking = get_object_or_404(
        Booking.objects.select_related("flight__airline", "passenger"),
        pk=booking_id,
        passenger=request.user,
    )
    boarding_pass = BoardingPass.objects.filter(booking=booking).first()
    window = get_check_in_window(booking.flight)
    can_check_in = (
        boarding_pass is None
        and booking.booking_status == "confirmed"
        and window["state"] == "open"
    )

    return render(
        request,
        "boarding/check_in.html",
        {
            "booking": booking,
            "boarding_pass": boarding_pass,
            "can_check_in": can_check_in,
            "check_in_window_state": window["state"],
            "check_in_opens_at": window["opens_at"],
            "check_in_closes_at": window["closes_at"],
        },
    )


@login_required
def boarding_pass_detail(request, pass_id):
    """Display a checked-in boarding pass to its passenger."""
    boarding_pass = get_object_or_404(
        BoardingPass.objects.select_related(
            "booking__passenger",
            "booking__flight__airline",
        ),
        pk=pass_id,
        booking__passenger=request.user,
        is_checked_in=True,
    )
    generate_qr_code(boarding_pass)
    return render(
        request,
        "boarding/boarding_pass.html",
        {"boarding_pass": boarding_pass},
    )


@login_required
@require_GET
def boarding_pass_qr(request, pass_id):
    """Serve the passenger's QR image from storage without relying on a public media URL."""
    boarding_pass = get_object_or_404(
        BoardingPass,
        pk=pass_id,
        booking__passenger=request.user,
        is_checked_in=True,
    )
    generate_qr_code(boarding_pass)
    image_file = boarding_pass.qr_code_image.open('rb')
    return FileResponse(image_file, content_type='image/png')


@login_required
def boarding_pass_print(request, pass_id):
    """Open the passenger's print-ready pass and trigger the browser dialog."""
    boarding_pass = get_object_or_404(
        BoardingPass.objects.select_related("booking__passenger"),
        pk=pass_id,
        booking__passenger=request.user,
        is_checked_in=True,
    )
    generate_qr_code(boarding_pass)
    return render(
        request,
        "boarding/boarding_pass.html",
        {"boarding_pass": boarding_pass, "print_mode": True},
    )


@login_required
@require_GET
def boarding_pass_pdf(request, pass_id):
    """Download a PDF copy of the signed-in passenger's boarding pass."""
    boarding_pass = get_object_or_404(
        BoardingPass.objects.select_related("booking__passenger"),
        pk=pass_id,
        booking__passenger=request.user,
        is_checked_in=True,
    )
    generate_qr_code(boarding_pass)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="boarding-pass-{boarding_pass.pk}.pdf"'
    page = canvas.Canvas(response, pagesize=A4)
    page_width, page_height = A4
    navy = colors.HexColor("#1a3c5e")
    green = colors.HexColor("#16a34a")
    muted = colors.HexColor("#64748b")

    page.setFillColor(navy)
    page.rect(0, page_height - 120, page_width, 120, fill=1, stroke=0)
    page.setFillColor(colors.white)
    page.setFont("Helvetica-Bold", 13)
    page.drawString(42, page_height - 48, "DKA DIGITAL BOARDING")
    page.setFont("Helvetica-Bold", 24)
    page.drawString(42, page_height - 84, "BOARDING PASS")
    page.setFont("Helvetica", 10)
    page.drawRightString(page_width - 42, page_height - 48, "CHECKED IN")

    page.setFillColor(muted)
    page.setFont("Helvetica-Bold", 9)
    page.drawString(42, page_height - 158, "AIRLINE")
    page.drawRightString(page_width - 42, page_height - 158, "FLIGHT")
    page.setFillColor(colors.black)
    page.setFont("Helvetica-Bold", 15)
    page.drawString(42, page_height - 181, boarding_pass.airline_name)
    page.drawRightString(page_width - 42, page_height - 181, boarding_pass.flight_number)

    page.setStrokeColor(colors.HexColor("#cbd5e1"))
    page.line(42, page_height - 202, page_width - 42, page_height - 202)
    page.setFillColor(navy)
    page.setFont("Helvetica-Bold", 24)
    page.drawString(42, page_height - 246, boarding_pass.origin)
    page.setFillColor(green)
    page.setFont("Helvetica-Bold", 12)
    page.drawCentredString(page_width / 2, page_height - 242, "TO")
    page.setFillColor(navy)
    page.setFont("Helvetica-Bold", 24)
    page.drawRightString(page_width - 42, page_height - 246, boarding_pass.destination)
    page.setFillColor(muted)
    page.setFont("Helvetica", 9)
    page.drawString(42, page_height - 262, "ORIGIN")
    page.drawRightString(page_width - 42, page_height - 262, "DESTINATION")

    def draw_field(x, y, label, value):
        page.setFillColor(muted)
        page.setFont("Helvetica-Bold", 8)
        page.drawString(x, y, label.upper())
        page.setFillColor(colors.black)
        page.setFont("Helvetica-Bold", 11)
        page.drawString(x, y - 17, str(value))

    draw_field(42, page_height - 315, "Passenger", boarding_pass.passenger_name)
    draw_field(42, page_height - 365, "Booking reference", boarding_pass.booking.booking_reference)
    draw_field(42, page_height - 415, "Date", boarding_pass.departure_date.strftime("%a, %d %b %Y"))
    draw_field(42, page_height - 465, "Departure", boarding_pass.departure_time.strftime("%I:%M %p").lstrip("0"))
    draw_field(220, page_height - 415, "Seat", boarding_pass.seat_number)
    draw_field(220, page_height - 465, "Gate", boarding_pass.gate)
    draw_field(220, page_height - 515, "Boarding time", boarding_pass.boarding_time.strftime("%I:%M %p").lstrip("0"))

    with boarding_pass.qr_code_image.open('rb') as qr_file:
        qr_image = ImageReader(BytesIO(qr_file.read()))
    page.drawImage(
        qr_image,
        page_width - 225,
        page_height - 545,
        width=180,
        height=180,
        preserveAspectRatio=True,
        mask="auto",
    )
    page.setFillColor(muted)
    page.setFont("Helvetica", 9)
    page.drawCentredString(page_width - 135, page_height - 565, "Present this QR code at the gate")
    page.setStrokeColor(colors.HexColor("#cbd5e1"))
    page.line(42, 72, page_width - 42, 72)
    page.setFillColor(muted)
    page.setFont("Helvetica", 9)
    page.drawCentredString(page_width / 2, 52, "Umaru Musa Yar’Adua Airport · Katsina (DKA)")
    page.save()
    return response
