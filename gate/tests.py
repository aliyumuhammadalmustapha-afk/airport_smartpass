import json
import uuid
from datetime import time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from boarding.models import BoardingPass
from flights.models import Airline, Booking, Flight
from gate.models import VerificationLog


class GateWorkflowTests(TestCase):
    def setUp(self):
        self.passenger = CustomUser.objects.create_user(
            username="passenger_test", email="passenger@example.test", password="test-pass"
        )
        self.staff = CustomUser.objects.create_user(
            username="gate_test", email="gate@example.test", password="test-pass", is_staff=True
        )
        self.admin = CustomUser.objects.create_superuser(
            username="admin_test", email="admin@example.test", password="test-pass"
        )
        airline = Airline.objects.create(name="Test Air", code="TA")
        flight = Flight.objects.create(
            airline=airline, flight_number="TA-001", origin="DKA", destination="ABJ",
            departure_date=timezone.localdate(),
            departure_time=time(9), arrival_time=time(10, 30),
        )
        booking = Booking.objects.create(
            passenger=self.passenger, flight=flight, booking_reference="TEST-BOOK-1", seat_number="1A"
        )
        self.boarding_pass = BoardingPass.objects.create(
            booking=booking, passenger_name="Test Passenger", flight_number=flight.flight_number,
            origin="DKA", destination="ABJ", departure_date=flight.departure_date,
            departure_time=flight.departure_time, seat_number="1A", boarding_time=time(8, 30),
            airline_name=airline.name, is_checked_in=True,
        )

    def verify(self, code):
        self.client.force_login(self.staff)
        return self.client.post(
            reverse("gate_verify"), data=json.dumps({"code": code}), content_type="application/json"
        )

    def test_scanner_requires_gate_staff(self):
        self.assertEqual(self.client.get(reverse("gate_scanner")).status_code, 302)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("gate_scanner"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "gate-scanner-body")
        self.assertContains(response, "Point the camera at the passenger")
        self.assertContains(response, 'id="qr-reader"')
        self.assertContains(response, 'id="session-scan-count"')
        self.assertContains(response, "gate@example.test")
        self.client.force_login(self.passenger)
        self.assertEqual(self.client.get(reverse("gate_scanner")).status_code, 302)

    def test_gate_login_allows_staff_and_rejects_passenger_and_admin(self):
        gate_login_url = reverse("gate_login")

        staff_response = self.client.post(
            gate_login_url,
            {"username": self.staff.email, "password": "test-pass"},
        )
        self.assertRedirects(staff_response, reverse("gate_scanner"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.staff.pk)

        self.client.logout()
        passenger_response = self.client.post(
            gate_login_url,
            {"username": self.passenger.email, "password": "test-pass"},
        )
        self.assertEqual(passenger_response.status_code, 200)
        self.assertContains(passenger_response, "does not have gate staff access")
        self.assertNotIn("_auth_user_id", self.client.session)

        admin_response = self.client.post(
            gate_login_url,
            {"username": self.admin.email, "password": "test-pass"},
        )
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, "does not have gate staff access")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_staff_scan_history_is_limited_to_current_user(self):
        other_staff = CustomUser.objects.create_user(
            username="other_gate", email="other-gate@example.test",
            password="test-pass", is_staff=True,
        )
        VerificationLog.objects.create(
            boarding_pass=self.boarding_pass,
            scanned_by=self.staff,
            result="VALID",
            scanned_code=str(self.boarding_pass.pass_code),
            notes="Own staff scan entry",
        )
        VerificationLog.objects.create(
            scanned_by=other_staff,
            result="INVALID",
            scanned_code="OTHER-STAFF-ONLY-CODE",
            notes="Other staff scan entry",
        )

        self.client.force_login(self.staff)
        response = self.client.get(reverse("gate_history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Scan History")
        self.assertContains(response, "Own staff scan entry")
        self.assertNotContains(response, "Other staff scan entry")
        self.assertNotContains(response, "OTHER-STAFF-ONLY-CODE")
        self.assertEqual(response.context["total_scans"], 1)
        self.assertEqual(response.context["valid_scans"], 1)

    def test_scan_history_requires_gate_staff(self):
        response = self.client.get(reverse("gate_history"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("gate_login"), response["Location"])

        self.client.force_login(self.passenger)
        response = self.client.get(reverse("gate_history"))
        self.assertEqual(response.status_code, 302)

    def test_valid_scan_marks_pass_used_and_creates_log(self):
        response = self.verify(str(self.boarding_pass.pass_code))
        self.assertEqual(response.json()["result"], "VALID")
        self.assertEqual(response.json()["passenger_name"], "Test Passenger")
        self.assertEqual(response.json()["flight_number"], "TA-001")
        self.assertEqual(response.json()["seat_number"], "1A")
        self.assertEqual(response.json()["gate"], "A1")
        self.assertIn("Verified at", response.json()["message"])
        self.boarding_pass.refresh_from_db()
        self.assertTrue(self.boarding_pass.is_used)
        log = VerificationLog.objects.get()
        self.assertEqual(log.scanned_by, self.staff)
        self.assertEqual(log.boarding_pass, self.boarding_pass)

    def test_repeat_scan_is_already_used_and_logged(self):
        self.verify(str(self.boarding_pass.pass_code))
        response = self.verify(str(self.boarding_pass.pass_code))
        self.assertEqual(response.json()["result"], "ALREADY_USED")
        self.assertIn("already verified at", response.json()["message"])
        self.assertIn("Do not allow re-entry", response.json()["message"])
        self.assertEqual(VerificationLog.objects.count(), 2)

    def test_pass_for_past_flight_is_expired_and_logged(self):
        self.boarding_pass.departure_date = timezone.localdate() - timedelta(days=1)
        self.boarding_pass.save(update_fields=["departure_date"])

        response = self.verify(str(self.boarding_pass.pass_code))

        self.assertEqual(response.json()["result"], "EXPIRED")
        self.assertIn("This pass is no longer valid", response.json()["message"])
        log = VerificationLog.objects.get()
        self.assertEqual(log.result, "EXPIRED")
        self.assertEqual(log.boarding_pass, self.boarding_pass)
        self.boarding_pass.refresh_from_db()
        self.assertFalse(self.boarding_pass.is_used)

    def test_pass_for_future_flight_is_not_approved_yet(self):
        self.boarding_pass.departure_date = timezone.localdate() + timedelta(days=1)
        self.boarding_pass.save(update_fields=["departure_date"])

        response = self.verify(str(self.boarding_pass.pass_code))

        self.assertEqual(response.json()["result"], "INVALID")
        self.assertIn("future flight", response.json()["message"])
        self.assertEqual(VerificationLog.objects.get().result, "INVALID")

    def test_unknown_uuid_is_invalid_and_logged_without_pass(self):
        response = self.verify(str(uuid.uuid4()))
        self.assertEqual(response.json()["result"], "INVALID")
        log = VerificationLog.objects.get()
        self.assertEqual(log.result, "INVALID")
        self.assertIsNone(log.boarding_pass)

    def test_invalid_qr_text_is_invalid_and_logged(self):
        response = self.verify("DKA-DEMO-INVALID-0001")
        self.assertEqual(response.json()["result"], "INVALID")
        self.assertEqual(VerificationLog.objects.get().scanned_code, "DKA-DEMO-INVALID-0001")

    def test_only_superuser_can_view_main_site_logs(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("verification_logs"))
        self.assertEqual(response.status_code, 200)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("verification_logs")).status_code, 403)


class AdminPanelTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(
            username="panel_admin", email="panel-admin@example.test", password="TestAdmin!8392"
        )
        self.passenger = CustomUser.objects.create_user(
            username="panel_passenger", email="panel-passenger@example.test", password="TestPass!8392"
        )
        self.airline = Airline.objects.create(name="Panel Test Air", code="PT")
        self.flight = Flight.objects.create(
            airline=self.airline,
            flight_number="PT-410",
            departure_date=timezone.localdate() + timedelta(days=4),
            departure_time=time(9),
            arrival_time=time(10, 30),
            total_seats=20,
            available_seats=20,
        )
        self.booking = Booking.objects.create(
            passenger=self.passenger,
            flight=self.flight,
            booking_reference="DKA-2026-TEST01",
            seat_number="1A",
        )
        self.flight.available_seats = 19
        self.flight.save(update_fields=["available_seats"])
        self.client.force_login(self.admin)

    def test_dashboard_shows_custom_admin_overview(self):
        response = self.client.get(reverse("admin_panel"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Airport Admin Dashboard")
        self.assertContains(response, "Flights Today")
        self.assertContains(response, "DKA Digital Admin")

    def test_custom_admin_pages_require_superuser(self):
        self.client.logout()
        response = self.client.get(reverse("admin_panel"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

        self.client.force_login(self.passenger)
        response = self.client.get(reverse("admin_panel_flights"))
        self.assertEqual(response.status_code, 302)

    def test_admin_login_redirects_to_custom_dashboard(self):
        self.client.logout()
        response = self.client.post(
            reverse("login"),
            {"username": self.admin.email, "password": "TestAdmin!8392"},
        )
        self.assertRedirects(response, reverse("admin_panel"))

    def test_admin_management_lists_forms_and_confirm_pages_render(self):
        staff_member = CustomUser.objects.create_user(
            username="panel_staff", email="panel-staff@example.test",
            password="TestStaff!8392", is_staff=True,
        )
        routes = [
            "admin_panel_flights", "admin_panel_flight_add",
            "admin_panel_flight_edit", "admin_panel_flight_cancel",
            "admin_panel_airlines", "admin_panel_airline_add",
            "admin_panel_airline_edit", "admin_panel_staff",
            "admin_panel_staff_add", "admin_panel_staff_edit",
            "admin_panel_bookings", "admin_panel_booking_cancel",
            "admin_panel_passes", "admin_panel_logs",
        ]
        route_args = {
            "admin_panel_flight_edit": [self.flight.pk],
            "admin_panel_flight_cancel": [self.flight.pk],
            "admin_panel_airline_edit": [self.airline.pk],
            "admin_panel_staff_edit": [staff_member.pk],
            "admin_panel_booking_cancel": [self.booking.pk],
        }

        for route_name in routes:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name, args=route_args.get(route_name, [])))
                self.assertEqual(response.status_code, 200)

    def test_admin_can_add_gate_staff_with_hashed_password(self):
        response = self.client.post(reverse("admin_panel_staff_add"), {
            "first_name": "New",
            "last_name": "Officer",
            "email": "new-officer@example.test",
            "phone_number": "08012345678",
            "password1": "StrongGate!54321",
            "password2": "StrongGate!54321",
        })
        self.assertRedirects(response, reverse("admin_panel_staff"))
        staff_member = CustomUser.objects.get(email="new-officer@example.test")
        self.assertTrue(staff_member.is_staff)
        self.assertFalse(staff_member.is_superuser)
        self.assertTrue(staff_member.check_password("StrongGate!54321"))
        self.assertNotEqual(staff_member.password, "StrongGate!54321")

    def test_admin_can_add_flight_and_initializes_available_seats(self):
        response = self.client.post(reverse("admin_panel_flight_add"), {
            "airline": self.airline.pk,
            "flight_number": "PT-411",
            "origin": "DKA",
            "destination": "ABJ",
            "departure_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
            "departure_time": "11:00",
            "arrival_time": "12:30",
            "total_seats": "24",
            "status": "scheduled",
        })
        self.assertRedirects(response, reverse("admin_panel_flights"))
        created_flight = Flight.objects.get(flight_number="PT-411")
        self.assertEqual(created_flight.available_seats, 24)

    def test_admin_can_edit_flight_and_cancel_it(self):
        response = self.client.post(reverse("admin_panel_flight_edit", args=[self.flight.pk]), {
            "airline": self.airline.pk,
            "flight_number": self.flight.flight_number,
            "origin": "DKA",
            "destination": "ABJ",
            "departure_date": (timezone.localdate() + timedelta(days=6)).isoformat(),
            "departure_time": "10:00",
            "arrival_time": "11:30",
            "total_seats": "25",
            "status": "scheduled",
        })
        self.assertRedirects(response, reverse("admin_panel_flights"))
        self.flight.refresh_from_db()
        self.assertEqual(self.flight.available_seats, 24)
        self.assertEqual(self.flight.total_seats, 25)

        response = self.client.post(reverse("admin_panel_flight_cancel", args=[self.flight.pk]))
        self.assertRedirects(response, reverse("admin_panel_flights"))
        self.flight.refresh_from_db()
        self.assertEqual(self.flight.status, "cancelled")

    def test_admin_can_add_and_edit_airline(self):
        response = self.client.post(reverse("admin_panel_airline_add"), {
            "name": "New Panel Airline", "code": "NP",
        })
        self.assertRedirects(response, reverse("admin_panel_airlines"))
        airline = Airline.objects.get(code="NP")

        response = self.client.post(reverse("admin_panel_airline_edit", args=[airline.pk]), {
            "name": "Updated Panel Airline", "code": "NP",
        })
        self.assertRedirects(response, reverse("admin_panel_airlines"))
        airline.refresh_from_db()
        self.assertEqual(airline.name, "Updated Panel Airline")

    def test_admin_can_edit_and_deactivate_gate_staff(self):
        staff_member = CustomUser.objects.create_user(
            username="panel_staff_edit", email="panel-staff-edit@example.test",
            password="TestStaff!8392", is_staff=True,
        )
        response = self.client.post(reverse("admin_panel_staff_edit", args=[staff_member.pk]), {
            "first_name": "Updated", "last_name": "Officer",
            "email": staff_member.email, "phone_number": "08087654321", "is_active": "on",
        })
        self.assertRedirects(response, reverse("admin_panel_staff"))
        staff_member.refresh_from_db()
        self.assertEqual(staff_member.first_name, "Updated")

        response = self.client.post(reverse("admin_panel_staff_toggle_active", args=[staff_member.pk]))
        self.assertRedirects(response, reverse("admin_panel_staff"))
        staff_member.refresh_from_db()
        self.assertFalse(staff_member.is_active)

    def test_admin_can_cancel_booking_and_release_its_seat(self):
        cancel_url = reverse("admin_panel_booking_cancel", args=[self.booking.pk])
        self.assertEqual(self.client.get(cancel_url).status_code, 200)
        response = self.client.post(cancel_url)
        self.assertRedirects(response, reverse("admin_panel_bookings"))
        self.booking.refresh_from_db()
        self.flight.refresh_from_db()
        self.assertEqual(self.booking.booking_status, "cancelled")
        self.assertEqual(self.flight.available_seats, 20)

    def test_admin_can_filter_verification_logs(self):
        VerificationLog.objects.create(
            scanned_by=self.admin,
            result="INVALID",
            scanned_code="FILTER-TEST-1",
            notes="Filtered scan log",
        )
        VerificationLog.objects.create(
            scanned_by=self.admin,
            result="VALID",
            scanned_code="FILTER-TEST-2",
            notes="Other scan log",
        )
        response = self.client.get(reverse("admin_panel_logs"), {"result": "INVALID"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Filtered scan log")
        self.assertNotContains(response, "Other scan log")

    def test_admin_can_delete_flight(self):
        delete_url = reverse("admin_panel_flight_delete", args=[self.flight.pk])
        confirm_page = self.client.get(delete_url)
        self.assertEqual(confirm_page.status_code, 200)
        self.assertContains(confirm_page, self.flight.flight_number)

        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse("admin_panel_flights"))
        self.assertFalse(Flight.objects.filter(pk=self.flight.pk).exists())

    def test_admin_can_delete_airline(self):
        delete_url = reverse("admin_panel_airline_delete", args=[self.airline.pk])
        confirm_page = self.client.get(delete_url)
        self.assertEqual(confirm_page.status_code, 200)

        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse("admin_panel_airlines"))
        self.assertFalse(Airline.objects.filter(pk=self.airline.pk).exists())

    def test_admin_can_delete_staff(self):
        staff_member = CustomUser.objects.create_user(
            username="panel_staff_del", email="panel-staff-del@example.test",
            password="TestStaff!8392", is_staff=True,
        )
        delete_url = reverse("admin_panel_staff_delete", args=[staff_member.pk])
        confirm_page = self.client.get(delete_url)
        self.assertEqual(confirm_page.status_code, 200)

        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse("admin_panel_staff"))
        self.assertFalse(CustomUser.objects.filter(pk=staff_member.pk).exists())


class GateStaffRoleAccessTests(TestCase):
    def setUp(self):
        self.staff_user = CustomUser.objects.create_user(
            username="gate_staff_role",
            email="staff.role@example.test",
            password="test-password-123",
            is_staff=True,
        )
        self.airline = Airline.objects.create(name="Max Air Katsina", code="VM")
        self.flight = Flight.objects.create(
            airline=self.airline,
            flight_number="VM-303",
            origin="DKA",
            destination="ABJ",
            departure_date=timezone.localdate(),
            departure_time=time(14, 0),
            arrival_time=time(15, 10),
            total_seats=50,
            available_seats=50,
            status="scheduled",
        )

    def test_gate_scanner_displays_today_departures(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("gate_scanner"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("departures_today", response.context)
        self.assertContains(response, "Today's Departures")
        self.assertContains(response, self.flight.flight_number)

    def test_gate_staff_redirected_away_from_passenger_flight_list(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("flight_list"))
        self.assertRedirects(response, reverse("gate_scanner"))

    def test_gate_staff_redirected_away_from_passenger_booking(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("book_flight", args=[self.flight.pk]))
        self.assertRedirects(response, reverse("gate_scanner"))
