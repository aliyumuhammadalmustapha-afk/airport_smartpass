from django.db import models
from django.conf import settings


class VerificationLog(models.Model):
    """
    Records every QR code scan attempt at the gate.
    Every scan — successful or not — is logged here.
    This is our audit trail.
    """
    
    RESULT_CHOICES = [
        ('VALID', 'Valid'),
        ('ALREADY_USED', 'Already Used'),
        ('INVALID', 'Invalid'),
        ('EXPIRED', 'Expired'),
    ]
    
    # Which boarding pass was scanned
    # null=True because INVALID scans have no matching boarding pass
    boarding_pass = models.ForeignKey(
        'boarding.BoardingPass',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verification_logs'
    )
    
    # Which staff member performed the scan
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='verifications_performed'
    )
    
    scanned_at = models.DateTimeField(auto_now_add=True)
    
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES
    )
    
    # The raw code that was scanned
    # useful for INVALID scans where no boarding pass record exists
    scanned_code = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.result} | {self.scanned_at} | {self.scanned_by}"
    
    class Meta:
        ordering = ['-scanned_at']  # newest scans appear first
