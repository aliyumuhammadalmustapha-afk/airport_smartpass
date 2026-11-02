from datetime import datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import CustomUser
from boarding.models import BoardingPass
from boarding.qr_codes import generate_qr_code
from boarding.utils import get_check_in_window
from flights.models import Airline, Booking, Flight


class OnlineCheckInTests(TestCase):
    def setUp(self):
        self.passenger = CustomUser.objects.create_user(
            username="checkin_passenger",
            email="checkin-passenger@example.test",
            password="test-password-123",
        )
        airline = Airline.objects.create(name="Check-in Test Air", code="CI")
        self.flight = Flight.objects.create(
            airline=airline,
            flight_number="CI-120",
            departure_date=timezone.localdate() + timedelta(days=3),
            departure_time=time(12),
            arrival_time=time(13, 30),
        )
        self.booking = Booking.objects.create(
            passenger=self.passenger,
            flight=self.flight,
            booking_reference="DKA-TEST-CHECKIN",
            seat_number="1A",
        )
        self.client.force_login(self.passenger)

    def test_window_uses_opening_and_closing_boundaries_in_wat(self):
        wat = ZoneInfo("Africa/Lagos")
        departure = datetime.combine(
            self.flight.departure_date,
            self.flight.departure_time,
        ).replace(tzinfo=wat)
        opens_at = departure - timedelta(hours=24)
        closes_at = departure - timedelta(hours=1)

        self.assertEqual(
            get_check_in_window(self.flight, opens_at - timedelta(minutes=1))["state"],
            "not_yet_open",
        )
        self.assertEqual(get_check_in_window(self.flight, opens_at)["state"], "open")
        self.assertEqual(
            get_check_in_window(self.flight, closes_at - timedelta(minutes=1))["state"],
            "open",
        )
        self.assertEqual(get_check_in_window(self.flight, closes_at)["state"], "closed")

    def test_get_and_post_outside_window_do_not_create_pass(self):
        page = self.client.get(reverse("check_in", args=[self.booking.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Online check-in opens 24 hours before departure")

        response = self.client.post(reverse("check_in", args=[self.booking.id]))
        self.assertRedirects(response, reverse("my_bookings"))
        self.assertFalse(BoardingPass.objects.filter(booking=self.booking).exists())

    @patch("boarding.views.generate_qr_code")
    def test_in_window_check_in_creates_only_one_pass(self, generate_qr):
        wat = ZoneInfo("Africa/Lagos")
        departure = timezone.now().astimezone(wat) + timedelta(hours=12)
        self.flight.departure_date = departure.date()
        self.flight.departure_time = departure.time().replace(tzinfo=None)
        self.flight.save(update_fields=["departure_date", "departure_time"])

        response = self.client.post(reverse("check_in", args=[self.booking.id]))
        self.assertRedirects(response, reverse("check_in", args=[self.booking.id]))
        boarding_pass = BoardingPass.objects.get(booking=self.booking)
        self.assertTrue(boarding_pass.is_checked_in)

        duplicate_response = self.client.post(reverse("check_in", args=[self.booking.id]))
        self.assertRedirects(duplicate_response, reverse("check_in", args=[self.booking.id]))
        self.assertEqual(BoardingPass.objects.filter(booking=self.booking).count(), 1)
        self.assertEqual(generate_qr.call_count, 2)

    def test_qr_png_is_reused_and_recreated_if_missing(self):
        boarding_pass = BoardingPass.objects.create(
            booking=self.booking,
            passenger_name="Test Passenger",
            flight_number=self.flight.flight_number,
            origin=self.flight.origin,
            destination=self.flight.destination,
            departure_date=self.flight.departure_date,
            departure_time=self.flight.departure_time,
            seat_number=self.booking.seat_number,
            boarding_time=time(11, 30),
            airline_name=self.flight.airline.name,
            is_checked_in=True,
        )

        with TemporaryDirectory() as media_directory:
            with override_settings(MEDIA_ROOT=media_directory):
                generated_file = generate_qr_code(boarding_pass)
                image_path = Path(generated_file.path)
                saved_name = generated_file.name
                self.assertTrue(image_path.is_file())
                with Image.open(image_path) as image:
                    self.assertEqual(image.format, "PNG")

                reused_file = generate_qr_code(boarding_pass)
                self.assertEqual(reused_file.name, saved_name)
                self.assertEqual(len(list(image_path.parent.glob("*.png"))), 1)

                image_path.unlink()
                regenerated_file = generate_qr_code(boarding_pass)
                self.assertTrue(Path(regenerated_file.path).is_file())

    def test_checked_in_pass_displays_ticket_qr_and_print_action(self):
        boarding_pass = BoardingPass.objects.create(
            booking=self.booking,
            passenger_name="Test Passenger",
            flight_number=self.flight.flight_number,
            origin=self.flight.origin,
            destination=self.flight.destination,
            departure_date=self.flight.departure_date,
            departure_time=self.flight.departure_time,
            seat_number=self.booking.seat_number,
            boarding_time=time(11, 30),
            airline_name=self.flight.airline.name,
            is_checked_in=True,
        )

        with TemporaryDirectory() as media_directory:
            with override_settings(MEDIA_ROOT=media_directory):
                response = self.client.get(
                    reverse("boarding_pass_detail", args=[boarding_pass.id])
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Your boarding pass is ready")
                self.assertContains(response, "Scan this QR code at the gate")
                self.assertContains(response, "Download PDF")
                self.assertContains(response, "Print Pass")
                self.assertContains(response, "government-issued ID")
                boarding_pass.refresh_from_db()
                self.assertTrue(Path(boarding_pass.qr_code_image.path).is_file())

    def test_checked_in_pass_downloads_as_pdf(self):
        boarding_pass = BoardingPass.objects.create(
            booking=self.booking,
            passenger_name="Test Passenger",
            flight_number=self.flight.flight_number,
            origin=self.flight.origin,
            destination=self.flight.destination,
            departure_date=self.flight.departure_date,
            departure_time=self.flight.departure_time,
            seat_number=self.booking.seat_number,
            boarding_time=time(11, 30),
            airline_name=self.flight.airline.name,
            is_checked_in=True,
        )

        with TemporaryDirectory() as media_directory:
            with override_settings(MEDIA_ROOT=media_directory):
                response = self.client.get(
                    reverse("boarding_pass_pdf", args=[boarding_pass.id])
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment; filename=\"boarding-pass-", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF-"))

    def test_pdf_download_requires_own_checked_in_pass(self):
        boarding_pass = BoardingPass.objects.create(
            booking=self.booking,
            passenger_name="Test Passenger",
            flight_number=self.flight.flight_number,
            origin=self.flight.origin,
            destination=self.flight.destination,
            departure_date=self.flight.departure_date,
            departure_time=self.flight.departure_time,
            seat_number=self.booking.seat_number,
            boarding_time=time(11, 30),
            airline_name=self.flight.airline.name,
            is_checked_in=True,
        )
        pdf_url = reverse("boarding_pass_pdf", args=[boarding_pass.id])
        other_passenger = CustomUser.objects.create_user(
            username="other_passenger",
            email="other-passenger@example.test",
            password="test-password-123",
        )

        self.client.force_login(other_passenger)
        self.assertEqual(self.client.get(pdf_url).status_code, 404)

        self.client.force_login(self.passenger)
        boarding_pass.is_checked_in = False
        boarding_pass.save(update_fields=["is_checked_in"])
        self.assertEqual(self.client.get(pdf_url).status_code, 404)
