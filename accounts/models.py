from django.contrib.auth.models import AbstractUser
from django.db import models



class CustomUser(AbstractUser):
    """
    Extended user model using email as the login field.
    """

    # Override the email field from AbstractUser
    # and make it unique so it can be used as USERNAME_FIELD
    email = models.EmailField(unique=True)

    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True
    )

    # Use email as the login field instead of username
    USERNAME_FIELD = 'email'

    # These are required when creating a superuser via command line
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"