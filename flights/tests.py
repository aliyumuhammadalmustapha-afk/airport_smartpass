from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from accounts.models import CustomUser
from flights.models import Airline, Booking, Flight


class SeedDemoDataCommandTests(TestCase):
    def test_seed_command_is_repeatable_and_preserves_existing_flights(self):
        with TemporaryDirectory() as media_directory:
            with override_settings(MEDIA_ROOT=Path(media_directory)):
                call_command("seed_demo_data", stdout=StringIO())
                self.assertEqual(Airline.objects.count(), 2)
                self.assertEqual(Flight.objects.count(), 6)

                seeded_flights = Flight.objects.select_related("airline")
                self.assertTrue(all(flight.origin == "DKA" for flight in seeded_flights))
                self.assertTrue(all(flight.destination == "ABJ" for flight in seeded_flights))
                invalid_qr_path = Path(media_directory) / "qrcodes" / "invalid_demo_qr.png"
                self.assertTrue(invalid_qr_path.is_file())
                with Image.open(invalid_qr_path) as image:
                    self.assertEqual(image.format, "PNG")

                passenger = CustomUser.objects.create_user(
                    username="seed_test_passenger",
                    email="seed-test@example.test",
                    password="SeedTest!8392",
                )
                flight = Flight.objects.get(flight_number="VM-401")
                original_date = flight.departure_date
                Booking.objects.create(
                    passenger=passenger,
                    flight=flight,
                    booking_reference="DKA-2026-SEED01",
                    seat_number="1A",
                )
                flight.available_seats = flight.total_seats - 1
                flight.save(update_fields=["available_seats"])

                call_command("seed_demo_data", stdout=StringIO())

                flight.refresh_from_db()
                self.assertEqual(Airline.objects.count(), 2)
                self.assertEqual(Flight.objects.count(), 6)
                self.assertEqual(flight.departure_date, original_date)
                self.assertEqual(flight.available_seats, flight.total_seats - 1)
