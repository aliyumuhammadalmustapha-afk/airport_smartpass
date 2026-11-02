from datetime import datetime, time, timedelta

import qrcode
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from flights.models import Airline, Flight


class Command(BaseCommand):
    help = "Ensure the DKA demo airlines, six flights, and invalid-scan QR are available."

    def handle(self, *args, **options):
        airlines = {}
        for code, name in (("VM", "Max Air"), ("RN", "Rano Air")):
            airlines[code], _ = Airline.objects.get_or_create(code=code, defaults={"name": name})

        today = timezone.localdate()
        schedule = (
            ("VM-401", "VM", 15, time(7), 60),
            ("VM-402", "VM", 17, time(12), 60),
            ("VM-403", "VM", 22, time(17), 60),
            ("RN-201", "RN", 18, time(8), 48),
            ("RN-202", "RN", 24, time(11), 48),
            ("RN-203", "RN", 26, time(15), 48),
        )
        for number, airline_code, day_offset, departure, seats in schedule:
            flight, created = Flight.objects.get_or_create(
                flight_number=number,
                defaults={
                    "airline": airlines[airline_code], "origin": "DKA", "destination": "ABJ",
                    "departure_date": today + timedelta(days=day_offset),
                    "departure_time": departure,
                    "arrival_time": (datetime.combine(today, departure) + timedelta(minutes=90)).time(),
                    "total_seats": seats, "available_seats": seats, "status": "scheduled",
                },
            )
            self.stdout.write(f"{'Created' if created else 'Kept'} {flight.flight_number}")

        qr_dir = settings.MEDIA_ROOT / "qrcodes"
        qr_dir.mkdir(parents=True, exist_ok=True)
        qrcode.make("DKA-DEMO-INVALID-0001").save(qr_dir / "invalid_demo_qr.png")
        self.stdout.write(self.style.SUCCESS("Invalid test QR saved to media/qrcodes/invalid_demo_qr.png"))

