import json
import uuid

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from boarding.models import BoardingPass
from flights.models import Flight

from .forms import GateStaffAuthenticationForm
from .models import VerificationLog


def gate_login(request):
    """Authenticate a user and grant the gate area only to staff accounts."""
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect("admin_panel")
        if request.user.is_staff:
            return redirect("gate_scanner")
        return render(request, "gate/login.html", {"access_denied": True}, status=403)

    form = GateStaffAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        staff_user = form.get_user()
        if staff_user.is_staff and not staff_user.is_superuser:
            login(request, staff_user)
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("gate_scanner")
        form.add_error(None, "This account does not have gate staff access.")
    return render(request, "gate/login.html", {"form": form, "next": next_url})


@user_passes_test(lambda user: user.is_staff and not user.is_superuser, login_url="gate_login")
def gate_scanner(request):
    """Show the QR camera scanner and today's active departures to authenticated gate staff."""
    today = timezone.localdate()
    departures_today = list(
        Flight.objects.filter(departure_date=today)
        .select_related("airline")
        .order_by("departure_time", "flight_number")
    )
    for flight in departures_today:
        flight.sync_status()

    return render(
        request,
        "gate/scanner.html",
        {
            "departures_today": departures_today,
            "today": today,
        },
    )


@user_passes_test(lambda user: user.is_staff and not user.is_superuser, login_url="gate_login")
def staff_scan_history(request):
    """Show only the scans performed by the signed-in gate staff member."""
    logs = VerificationLog.objects.filter(scanned_by=request.user).select_related(
        "boarding_pass"
    )
    return render(
        request,
        "gate/scan_history.html",
        {
            "logs": logs,
            "total_scans": logs.count(),
            "valid_scans": logs.filter(result="VALID").count(),
            "used_scans": logs.filter(result="ALREADY_USED").count(),
            "invalid_scans": logs.filter(result="INVALID").count(),
            "expired_scans": logs.filter(result="EXPIRED").count(),
        },
    )


@user_passes_test(lambda user: user.is_staff and not user.is_superuser, login_url="gate_login")
@require_POST
def verify_qr(request):
    """Verify one scanned pass and record its result for the audit trail with detailed diagnostics."""
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    scanned_code = payload.get("code") if isinstance(payload, dict) else None
    if not isinstance(scanned_code, str) or not scanned_code.strip():
        return JsonResponse({"error": "A QR code is required."}, status=400)
    scanned_code = scanned_code.strip()

    try:
        pass_code = uuid.UUID(scanned_code)
    except (ValueError, AttributeError):
        VerificationLog.objects.create(
            scanned_by=request.user,
            result="INVALID",
            scanned_code=scanned_code[:255],
            notes="The scanned text is not a valid UUID.",
        )
        return JsonResponse({
            "result": "INVALID",
            "reason_type": "MALFORMED_CODE",
            "message": "This QR code is not a valid boarding pass format.",
        })

    response_details = {}
    with transaction.atomic():
        boarding_pass = (
            BoardingPass.objects.select_for_update()
            .select_related("booking__flight", "booking__passenger")
            .filter(pass_code=pass_code)
            .first()
        )

        today = timezone.localdate()

        if boarding_pass is None:
            result = "INVALID"
            reason_type = "NOT_FOUND"
            message = "Unrecognized QR code. No matching boarding pass found in airport system."
            notes = "No eligible checked-in boarding pass matched this code."
        else:
            # Populate passenger and flight details whenever pass exists
            response_details = {
                "passenger_name": boarding_pass.passenger_name,
                "flight_number": boarding_pass.flight_number,
                "seat_number": boarding_pass.seat_number,
                "gate": boarding_pass.gate,
                "departure_date": boarding_pass.departure_date.strftime("%d %b %Y"),
                "departure_time": boarding_pass.departure_time.strftime("%H:%M"),
            }

            flight_date = boarding_pass.departure_date.strftime("%d %b %Y")
            today_str = today.strftime("%d %b %Y")

            if boarding_pass.departure_date < today:
                result = "EXPIRED"
                reason_type = "EXPIRED_PAST_DATE"
                message = f"This boarding pass was for {flight_date}. Today is {today_str}. This pass is no longer valid."
                notes = "The flight date has passed."
            elif boarding_pass.departure_date > today:
                result = "INVALID"
                reason_type = "FUTURE_FLIGHT_DATE"
                message = f"This pass is for a future flight on {flight_date}; it is not valid today."
                notes = f"The flight date has not arrived yet ({flight_date})."
            elif boarding_pass.booking.flight.status == "cancelled":
                result = "INVALID"
                reason_type = "FLIGHT_CANCELLED"
                message = f"Flight {boarding_pass.flight_number} has been cancelled. Passenger cannot board."
                notes = "The flight associated with this boarding pass is cancelled."
            elif boarding_pass.booking.flight.status == "departed":
                result = "INVALID"
                reason_type = "FLIGHT_DEPARTED"
                message = f"Flight {boarding_pass.flight_number} has already departed. Gate is closed."
                notes = "The flight has already departed."
            elif boarding_pass.booking.booking_status == "cancelled":
                result = "INVALID"
                reason_type = "BOOKING_CANCELLED"
                message = f"The booking for {boarding_pass.passenger_name} was cancelled. Passenger cannot board."
                notes = "The booking for this pass was cancelled."
            elif not boarding_pass.is_checked_in:
                result = "INVALID"
                reason_type = "NOT_CHECKED_IN"
                message = "This boarding pass has not completed check-in."
                notes = "Pass record exists but is_checked_in is False."
            elif boarding_pass.is_used:
                result = "ALREADY_USED"
                reason_type = "ALREADY_SCANNED"
                used_at = timezone.localtime(boarding_pass.used_at).strftime("%I:%M %p")
                message = f"This boarding pass was already verified at {used_at} today. Do not allow re-entry."
                notes = f"Boarding pass scanned again after already being verified at {used_at}."
                response_details["used_at"] = used_at
            else:
                now = timezone.now()
                boarding_pass.is_used = True
                boarding_pass.used_at = now
                boarding_pass.save(update_fields=["is_used", "used_at"])
                result = "VALID"
                reason_type = "APPROVED"
                verified_at = timezone.localtime(now).strftime("%I:%M %p")
                message = f"Verified at {verified_at}. Passenger may proceed to aircraft."
                notes = "Boarding pass verified and marked as used."
                response_details["verified_at"] = verified_at

        VerificationLog.objects.create(
            boarding_pass=boarding_pass,
            scanned_by=request.user,
            result=result,
            scanned_code=scanned_code[:255],
            notes=notes,
        )

    return JsonResponse({
        "result": result,
        "reason_type": reason_type,
        "message": message,
        **response_details,
    })


@login_required
def verification_logs(request):
    """Administrator view of gate verification logs."""
    if not request.user.is_superuser:
        return HttpResponseForbidden("Administrator access is required to view scan logs.")
    logs = VerificationLog.objects.select_related(
        "boarding_pass", "scanned_by"
    ).order_by("-scanned_at")
    return render(request, "gate/verification_logs.html", {"logs": logs})
