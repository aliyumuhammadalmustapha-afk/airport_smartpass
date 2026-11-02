from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.db import models
from django.conf import settings
from django.utils import timezone

AIRPORT_TIME_ZONE = ZoneInfo("Africa/Lagos")


class Airline(models.Model):
    """
    Represents an airline operating at Katsina Airport.
    For this project: Max Air and Rano Air.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Flight(models.Model):
    """
    Represents a specific flight on a specific date.
    All flights are Katsina (DKA) to Abuja (ABJ).
    """
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('boarding', 'Boarding'),
        ('departed', 'Departed'),
        ('cancelled', 'Cancelled'),
    ]

    airline = models.ForeignKey(
        Airline,
        on_delete=models.CASCADE,
        related_name='flights'
    )
    flight_number = models.CharField(max_length=20, unique=True)
    origin = models.CharField(max_length=10, default='DKA')
    destination = models.CharField(max_length=10, default='ABJ')
    departure_date = models.DateField()
    departure_time = models.TimeField()
    arrival_time = models.TimeField()
    total_seats = models.PositiveIntegerField(default=60)
    available_seats = models.PositiveIntegerField(default=60)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled'
    )

    def get_dynamic_status(self, now=None):
        """Calculate the real-time flight status based on departure date/time in WAT."""
        if self.status == 'cancelled':
            return 'cancelled'
        now = now or timezone.now()
        if timezone.is_naive(now):
            now = now.replace(tzinfo=AIRPORT_TIME_ZONE)
        now_wat = now.astimezone(AIRPORT_TIME_ZONE)

        departure_wat = datetime.combine(
            self.departure_date,
            self.departure_time,
        ).replace(tzinfo=AIRPORT_TIME_ZONE)

        boarding_opens_wat = departure_wat - timedelta(minutes=45)

        if now_wat >= departure_wat:
            return 'departed'
        elif now_wat >= boarding_opens_wat:
            return 'boarding'
        else:
            return 'scheduled'

    def sync_status(self, save=True):
        """Ensure the stored status matches real-time progression."""
        current = self.get_dynamic_status()
        if self.status != current:
            self.status = current
            if save and self.pk:
                self.save(update_fields=['status'])
        return self.status

    def save(self, *args, **kwargs):
        if not self.status:
            self.status = self.get_dynamic_status()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.flight_number} | {self.origin} → {self.destination} | {self.departure_date}"


class Booking(models.Model):
    """
    Represents a passenger booking a specific flight.
    """
    STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]

    passenger = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    flight = models.ForeignKey(
        Flight,
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    booking_reference = models.CharField(
        max_length=20,
        unique=True,
        blank=True
    )
    seat_number = models.CharField(max_length=5)
    booking_date = models.DateTimeField(auto_now_add=True)
    booking_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='confirmed'
    )

    def __str__(self):
        return f"{self.booking_reference} | {self.passenger} | {self.flight}"
