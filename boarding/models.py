from django.db import models
from django.conf import settings
import uuid


class BoardingPass(models.Model):
    """
    Represents a digital boarding pass.
    Created when a passenger successfully checks in.
    Has a one-to-one relationship with Booking —
    meaning one booking produces exactly one boarding pass.
    The pass_code (UUID) is what gets encoded into the QR code.
    """
    
    # OneToOneField enforces: one booking = one boarding pass
    # at the database level. You cannot create two boarding
    # passes for the same booking.
    booking = models.OneToOneField(
        'flights.Booking',
        on_delete=models.CASCADE,
        related_name='boarding_pass'
    )
    
    # This UUID is the secret code inside the QR
    # uuid.uuid4 generates something like:
    # a3f8c2d1-7b4e-4f2a-9c1d-8e3f2b1a0c5d
    pass_code = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False  # prevents anyone from changing it manually
    )
    
    # We copy these from the booking/flight at check-in time
    # so the boarding pass is a permanent snapshot
    passenger_name = models.CharField(max_length=200)
    flight_number = models.CharField(max_length=20)
    origin = models.CharField(max_length=10)
    destination = models.CharField(max_length=10)
    departure_date = models.DateField()
    departure_time = models.TimeField()
    seat_number = models.CharField(max_length=5)
    gate = models.CharField(max_length=10, default='A1')
    boarding_time = models.TimeField()
    airline_name = models.CharField(max_length=100)
    
    # Path to the generated QR code image file
    qr_code_image = models.ImageField(
        upload_to='qrcodes/',
        blank=True,
        null=True
    )
    
    # Check-in tracking
    is_checked_in = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    
    # Gate scan tracking
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"BP-{self.pass_code} | {self.passenger_name} | {self.flight_number}"