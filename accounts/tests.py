from datetime import time
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from flights.models import Airline, Flight


class HomeViewTests(TestCase):
    def setUp(self):
        self.airline = Airline.objects.create(name="Max Air", code="VM")
        self.flight = Flight.objects.create(
            airline=self.airline,
            flight_number="VM-101",
            origin="DKA",
            destination="ABJ",
            departure_date=timezone.localdate(),
            departure_time=time(10, 30),
            arrival_time=time(11, 45),
            total_seats=60,
            available_seats=60,
            status="scheduled",
        )

    def test_home_page_renders_successfully(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Umaru Musa Yar'Adua Airport")
        self.assertContains(response, self.flight.flight_number)
        self.assertIn("upcoming_flights", response.context)


class PassengerAccountPersistenceTests(TestCase):
    def test_registered_passenger_can_log_in_again_after_a_new_request(self):
        registration = self.client.post(
            reverse("register"),
            {
                "first_name": "Test",
                "last_name": "Passenger",
                "email": "persistent-passenger@example.test",
                "phone_number": "08000000000",
                "password1": "SecureTestPass!2026",
                "password2": "SecureTestPass!2026",
            },
        )

        self.assertRedirects(registration, reverse("flight_list"))
        passenger = CustomUser.objects.get(email="persistent-passenger@example.test")
        self.assertTrue(passenger.check_password("SecureTestPass!2026"))

        self.client.post(reverse("logout"))
        login_response = self.client.post(
            reverse("login"),
            {"username": passenger.email, "password": "SecureTestPass!2026"},
        )

        self.assertRedirects(login_response, reverse("flight_list"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), passenger.pk)
