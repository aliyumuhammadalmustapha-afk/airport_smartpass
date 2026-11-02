import uuid

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.models import CustomUser
from flights.models import Airline, Booking, Flight


class AirportModelForm(forms.ModelForm):
    """Apply the shared form-control styling to admin model forms."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            current = field.widget.attrs.get("class", "")
            control = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = f"{current} {control}".strip()


class FlightAdminForm(AirportModelForm):
    status = forms.ChoiceField(
        choices=[("", "Auto-calculated based on time")] + Flight.STATUS_CHOICES,
        required=False,
        help_text="Leave as Auto-calculated for dynamic updates based on departure time, or select an override.",
    )

    class Meta:
        model = Flight
        fields = (
            "airline", "flight_number", "origin", "destination", "departure_date",
            "departure_time", "arrival_time", "total_seats", "status",
        )
        widgets = {
            "departure_date": forms.DateInput(attrs={"type": "date"}),
            "departure_time": forms.TimeInput(attrs={"type": "time"}),
            "arrival_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["status"].initial = self.instance.status
        else:
            self.fields["status"].initial = "scheduled"

    def clean_total_seats(self):
        total_seats = self.cleaned_data["total_seats"]
        if self.instance.pk:
            confirmed_bookings = Booking.objects.filter(
                flight=self.instance, booking_status="confirmed"
            ).count()
            if total_seats < confirmed_bookings:
                raise forms.ValidationError(
                    f"This flight already has {confirmed_bookings} confirmed bookings. "
                    "Total seats cannot be lower than that number."
                )
        return total_seats

    def save(self, commit=True):
        flight = super().save(commit=False)
        selected_status = self.cleaned_data.get("status")
        if selected_status:
            flight.status = selected_status
        else:
            flight.status = flight.get_dynamic_status()

        confirmed_bookings = (
            Booking.objects.filter(flight=flight, booking_status="confirmed").count()
            if flight.pk else 0
        )
        flight.available_seats = max(0, flight.total_seats - confirmed_bookings)
        if commit:
            flight.save()
            self.save_m2m()
        return flight


class AirlineAdminForm(AirportModelForm):
    class Meta:
        model = Airline
        fields = ("name", "code")


class GateStaffCreateForm(forms.Form):
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")
    email = forms.EmailField(label="Staff email")
    phone_number = forms.CharField(max_length=15, required=False, label="Phone number")
    password1 = forms.CharField(
        label="Temporary password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    password2 = forms.CharField(
        label="Confirm password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password1")
        confirmation = cleaned.get("password2")
        if password and confirmation and password != confirmation:
            self.add_error("password2", "The passwords do not match.")
        if password:
            candidate = CustomUser(
                email=cleaned.get("email", ""),
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
            )
            try:
                validate_password(password, user=candidate)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        username = f"gate_{uuid.uuid4().hex[:12]}"
        return CustomUser.objects.create_user(
            username=username,
            email=email,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            phone_number=self.cleaned_data["phone_number"],
            password=self.cleaned_data["password1"],
            is_staff=True,
            is_active=True,
        )


class GateStaffEditForm(AirportModelForm):
    new_password = forms.CharField(
        label="Change password (leave blank to keep current)",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name", "email", "phone_number", "is_active")
        widgets = {"is_active": forms.CheckboxInput(attrs={"class": "form-check-input"})}

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_new_password(self):
        password = self.cleaned_data.get("new_password")
        if password:
            validate_password(password, user=self.instance)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        new_password = self.cleaned_data.get("new_password")
        if new_password:
            user.set_password(new_password)
        if commit:
            user.save()
        return user
