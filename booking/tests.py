from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Appointment, Doctor, Slot, Specialty

User = get_user_model()


def fixtures():
    specialty = Specialty.objects.create(name="Cardiology")
    doctor = Doctor.objects.create(
        account=User.objects.create_user("doctor"), name="Dr. Rao", specialty=specialty,
        experience=10, fee=750, bio="Cardiology consultations.",
    )
    slot = Slot.objects.create(
        doctor=doctor, date=timezone.localdate() + timedelta(days=1),
        start_time=time(14), end_time=time(14, 30),
    )
    return doctor, slot, User.objects.create_user("patient"), User.objects.create_user("other")


class WorkflowTests(TestCase):
    client_class = APIClient

    def setUp(self):
        self.doctor, self.slot, self.patient, self.other = fixtures()
        self.payload = {"slot": self.slot.pk, "reason": "Follow-up"}
        self.client.force_login(self.patient)

    def available(self):
        response = self.client.get("/api/availability/", {"doctor": self.doctor.pk, "date": self.slot.date})
        return [slot["id"] for slot in response.json()]

    def test_booking_hides_slot_and_cancellation_releases_it(self):
        self.assertIn(self.slot.pk, self.available())
        visit = self.client.post("/api/appointments/", self.payload, format="json")
        self.assertEqual(visit.status_code, 201)
        self.assertNotIn(self.slot.pk, self.available())
        url = f"/api/appointments/{visit.json()['id']}/cancel/"
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.patient)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertIn(self.slot.pk, self.available())
        self.assertEqual(self.client.post(url).status_code, 409)
        self.assertEqual(self.client.post("/api/appointments/", self.payload, format="json").status_code, 201)

    def test_same_patient_cannot_book_two_doctors_at_the_same_time(self):
        self.assertEqual(self.client.post("/api/appointments/", self.payload, format="json").status_code, 201)
        second = Doctor.objects.create(
            account=User.objects.create_user("doctor2"), name="Dr. Iyer", specialty=self.doctor.specialty,
            experience=5, fee=600, bio="Consultations.",
        )
        other_slot = Slot.objects.create(
            doctor=second, date=self.slot.date, start_time=self.slot.start_time, end_time=self.slot.end_time,
        )
        self.assertEqual(self.client.post("/api/appointments/", {
            "slot": other_slot.pk, "reason": "Checkup",
        }, format="json").status_code, 409)

    def test_cancellation_limit_and_completion(self):
        visit = self.client.post("/api/appointments/", self.payload, format="json").json()["id"]
        with patch("booking.views.timezone.now", return_value=self.slot.starts_at - timedelta(minutes=119)):
            self.assertEqual(self.client.post(f"/api/appointments/{visit}/cancel/").status_code, 409)
        self.client.force_login(self.doctor.account)
        url = f"/api/appointments/{visit}/complete/"
        self.assertEqual(self.client.post(url, {"notes": "Reviewed"}, format="json").status_code, 409)
        with patch("booking.views.timezone.now", return_value=self.slot.starts_at + timedelta(minutes=1)):
            self.assertEqual(self.client.post(url, {"notes": "Reviewed"}, format="json").status_code, 200)
            self.assertEqual(self.client.post(url, {"notes": "Changed"}, format="json").status_code, 409)
            self.assertEqual(self.client.get("/api/dashboard/").json()["completed"], 1)
        self.assertEqual(Appointment.objects.get(pk=visit).notes, "Reviewed")

    def test_slot_validation_and_role_boundaries(self):
        data = {"date": self.slot.date.isoformat(), "start_time": "14:15", "end_time": "14:45"}
        self.assertEqual(self.client.post("/api/doctor/slots/", data, format="json").status_code, 403)
        self.client.force_login(self.doctor.account)
        self.assertEqual(self.client.post("/api/appointments/", self.payload, format="json").status_code, 403)
        self.assertEqual(self.client.get("/api/directory/").status_code, 403)
        self.assertEqual(self.client.post("/api/doctor/slots/", data, format="json").status_code, 409)
        data.update(start_time="14:30", end_time="15:00")
        url = "/api/doctor/slots/"
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        record_url = f"{url}{response.json()['id']}/"
        data.update(start_time="15:00", end_time="15:30")
        self.assertEqual(self.client.put(record_url, data, format="json").status_code, 200)
        self.assertEqual(self.client.delete(record_url).status_code, 204)
        data["date"] = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.assertEqual(self.client.post(url, data, format="json").status_code, 400)

    def test_authentication_and_csrf(self):
        browser = APIClient(enforce_csrf_checks=True)
        data = {"username": "newpatient", "password1": "Three-Random-Buildings!7",
                "password2": "Three-Random-Buildings!7"}
        self.assertEqual(browser.post("/api/auth/register/", data, format="json").status_code, 403)
        browser.get("/")
        browser.credentials(HTTP_X_CSRFTOKEN=browser.cookies["csrftoken"].value)
        self.assertEqual(browser.post("/api/auth/register/", data, format="json").status_code, 201)
        self.assertEqual(browser.get("/api/session/").json()["role"], "patient")
        browser.credentials(HTTP_X_CSRFTOKEN=browser.cookies["csrftoken"].value)
        self.assertEqual(browser.post("/api/auth/logout/").status_code, 200)
        self.assertIsNone(browser.get("/api/session/").json()["role"])


class ConcurrentBookingTests(TransactionTestCase):
    def test_only_one_concurrent_request_can_book_a_slot(self):
        # The default test database is shared in-memory SQLite. Use a file database
        # for this test so worker connections exercise normal SQLite lock waiting.
        _, slot, patient, other = fixtures()
        barrier = Barrier(2)
        clients = [APIClient(), APIClient()]
        for browser, user in zip(clients, (patient, other)):
            browser.force_login(user)

        def book_at_once(browser):
            try:
                barrier.wait(timeout=5)
                return browser.post("/api/appointments/", {
                    "slot": slot.pk, "reason": "Checkup",
                }, format="json").status_code
            finally:
                connections.close_all()

        self.assertFalse(connection.is_in_memory_db())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(book_at_once, clients))
        self.assertEqual(sorted(results), [201, 409])
        self.assertEqual(Appointment.objects.filter(slot=slot).count(), 1)
