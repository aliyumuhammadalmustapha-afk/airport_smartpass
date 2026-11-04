from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from flights.models import Flight, Booking
from .forms import PassengerAuthenticationForm, PassengerRegistrationForm


def home(request):
    """Display the public homepage with booking lookup support."""
    if request.method == "POST":
        ref = request.POST.get("booking_reference", "").strip().upper()
        if ref:
            if not request.user.is_authenticated:
                messages.info(request, "Please sign in with the account used to make this booking, then enter your reference again.")
                return redirect("login")

            booking = Booking.objects.filter(
                booking_reference=ref,
                passenger=request.user,
                booking_status="confirmed",
            ).first()
            if booking:
                if hasattr(booking, "boarding_pass") and booking.boarding_pass.is_checked_in:
                    return redirect("boarding_pass_detail", pass_id=booking.boarding_pass.id)
                return redirect("check_in", booking_id=booking.id)
            messages.error(request, "We couldn't find an active booking with that reference for your account. Check the reference and sign in with the account used to book.")
    
    upcoming_flights = Flight.objects.select_related("airline").filter(
        departure_date__gte=timezone.localdate()
    ).order_by("departure_date", "departure_time")[:6]
    
    for flight in upcoming_flights:
        flight.sync_status()
        
    return render(request, "home.html", {"upcoming_flights": upcoming_flights})


def register(request):
    """Create a passenger account and sign the passenger in."""
    if request.user.is_authenticated:
        return render(request, "accounts/register.html", {"already_signed_in": True})
    if request.method == "POST":
        form = PassengerRegistrationForm(request.POST)
        if form.is_valid():
            passenger = form.save()
            login(request, passenger)
            name = passenger.get_full_name().strip() or passenger.email
            messages.success(
                request,
                f"Account created successfully! Welcome, {name}. You can now browse available flights and book your trip.",
            )
            return redirect("flight_list")
    else:
        form = PassengerRegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    """Authenticate passengers, gate staff, or administrators by account role."""
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect("admin_panel")
        if request.user.is_staff:
            return redirect("gate_scanner")
        return redirect("flight_list")

    form = PassengerAuthenticationForm(request, data=request.POST or None)
    next_url = request.POST.get("next") or request.GET.get("next")
    if request.method == "POST" and form.is_valid():
        account = form.get_user()
        login(request, account)
        if account.is_superuser:
            return redirect("admin_panel")
        if account.is_staff:
            return redirect("gate_scanner")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect("flight_list")
    return render(request, "accounts/login.html", {"form": form, "next": next_url or ""})


@require_POST
def logout_view(request):
    """End the current login session and return to the login page."""
    logout(request)
    return redirect("login")
