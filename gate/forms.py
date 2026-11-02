from django.contrib.auth.forms import AuthenticationForm


class GateStaffAuthenticationForm(AuthenticationForm):
    """Collect the email and password used for gate staff login."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Staff email address"
        self.fields["username"].widget.attrs.update({"class": "form-control", "autocomplete": "email"})
        self.fields["password"].widget.attrs.update({"class": "form-control", "autocomplete": "current-password"})
