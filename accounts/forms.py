import uuid

from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import CustomUser


class PassengerRegistrationForm(UserCreationForm):
    """Collect passenger details and let Django securely create the account."""

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("first_name", "last_name", "email", "phone_number")
        labels = {
            "first_name": "First name",
            "last_name": "Last name",
            "email": "Email address",
            "phone_number": "Phone number",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

        self.fields["first_name"].widget.attrs.update({"autocomplete": "given-name"})
        self.fields["last_name"].widget.attrs.update({"autocomplete": "family-name"})
        self.fields["email"].widget.attrs.update({"autocomplete": "email", "inputmode": "email"})
        self.fields["phone_number"].widget.attrs.update({"autocomplete": "tel", "inputmode": "tel"})
        self.fields["password1"].widget.attrs.update({"autocomplete": "new-password"})
        self.fields["password2"].widget.attrs.update({"autocomplete": "new-password"})

    def save(self, commit=True):
        """Create a secure password and an internal username the passenger need not choose."""
        passenger = super().save(commit=False)
        while True:
            username = f"passenger_{uuid.uuid4().hex[:12]}"
            if not CustomUser.objects.filter(username=username).exists():
                passenger.username = username
                break

        if commit:
            passenger.save()
            self.save_m2m()
        return passenger


class PassengerAuthenticationForm(AuthenticationForm):
    """Authenticate passengers with their email address and password."""

    error_messages = {
        "invalid_login": _("Incorrect email or password. Please try again."),
        "inactive": _("This account is inactive."),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email address"
        self.fields["username"].widget.attrs.update({"class": "form-control", "autocomplete": "email"})
        self.fields["password"].widget.attrs.update({"class": "form-control", "autocomplete": "current-password"})
