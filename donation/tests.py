from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import Alert, Appointment, Donor, InventoryItem, RecipientCase


class AuthenticatedTestCase(TestCase):
    """Base class that logs in a coordinator account before each test."""

    def setUp(self):
        self.user = User.objects.create_user("coordinator", password="test-pass-12345")
        self.client.force_login(self.user)


class AuthTests(TestCase):
    def test_home_redirects_anonymous_to_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/login/"))

    def test_api_returns_401_for_anonymous(self):
        get = self.client.get("/api/state/")
        self.assertEqual(get.status_code, 401)
        post = self.client.post("/api/alerts/", {}, content_type="application/json")
        self.assertEqual(post.status_code, 401)

    def test_login_page_renders(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")

    def test_login_flow(self):
        User.objects.create_user("coordinator", password="test-pass-12345")
        response = self.client.post(
            "/login/", {"username": "coordinator", "password": "test-pass-12345"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_logout_redirects_to_login(self):
        user = User.objects.create_user("coordinator", password="test-pass-12345")
        self.client.force_login(user)
        response = self.client.post("/logout/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/login/")


class HomePageTests(AuthenticatedTestCase):
    def test_home_renders_and_sets_csrf_cookie(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LifeBridge")
        self.assertIn("csrftoken", response.cookies)

    def test_robots_and_sitemap(self):
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn("text/plain", robots["Content-Type"])
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn("xml", sitemap["Content-Type"])


class StateApiTests(AuthenticatedTestCase):
    def test_state_returns_all_sections(self):
        response = self.client.get("/api/state/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in ("donors", "cases", "inventory", "appointments", "alerts", "demoMode"):
            self.assertIn(key, payload)

    def test_demo_mode_seeds_data(self):
        self.client.get("/api/state/")
        self.assertTrue(Donor.objects.exists())
        self.assertTrue(InventoryItem.objects.exists())

    @override_settings(DEMO_MODE=False)
    def test_no_seed_outside_demo_mode(self):
        self.client.get("/api/state/")
        self.assertFalse(Donor.objects.exists())

    def test_state_rejects_post(self):
        self.assertEqual(self.client.post("/api/state/").status_code, 405)


class DonorApiTests(AuthenticatedTestCase):
    def test_create_donor(self):
        response = self.client.post(
            "/api/donors/",
            {
                "name": "Ama Serwaa",
                "donor_type": "Blood",
                "blood_type": "O+",
                "region": "Volta",
                "phone": "+233 20 000 0000",
                "organs": [],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "Ama Serwaa")
        self.assertTrue(Donor.objects.filter(name="Ama Serwaa").exists())

    def test_rejects_missing_name(self):
        response = self.client.post(
            "/api/donors/",
            {"blood_type": "O+", "region": "Volta", "phone": "123"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["errors"])

    def test_rejects_invalid_blood_type(self):
        response = self.client.post(
            "/api/donors/",
            {"name": "X", "blood_type": "Z+", "region": "Volta", "phone": "123"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("blood_type", response.json()["errors"])

    def test_rejects_invalid_organs(self):
        response = self.client.post(
            "/api/donors/",
            {"name": "X", "blood_type": "O+", "region": "V", "phone": "1", "organs": ["Brain"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_malformed_json(self):
        response = self.client.post("/api/donors/", "not json", content_type="application/json")
        self.assertEqual(response.status_code, 400)


class CaseApiTests(AuthenticatedTestCase):
    def test_create_case_also_creates_alert(self):
        response = self.client.post(
            "/api/cases/",
            {
                "recipient": "Kofi Mensah",
                "need_type": "Organ",
                "priority": "Critical",
                "blood_type": "B+",
                "organ": "Kidney",
                "hospital": "Ridge Hospital",
                "region": "Greater Accra",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["case"]["recipient"], "Kofi Mensah")
        self.assertEqual(payload["alert"]["level"], "Critical")
        self.assertTrue(Alert.objects.filter(title__icontains="Critical organ case").exists())

    def test_organ_case_requires_organ(self):
        response = self.client.post(
            "/api/cases/",
            {
                "recipient": "Kofi",
                "need_type": "Organ",
                "priority": "High",
                "blood_type": "B+",
                "hospital": "Ridge",
                "region": "Accra",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("organ", response.json()["errors"])

    def test_blood_case_ignores_organ(self):
        response = self.client.post(
            "/api/cases/",
            {
                "recipient": "Kofi",
                "need_type": "Blood",
                "priority": "Standard",
                "blood_type": "B+",
                "organ": "Kidney",
                "hospital": "Ridge",
                "region": "Accra",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["case"]["organ"], "")


class AppointmentApiTests(AuthenticatedTestCase):
    def setUp(self):
        super().setUp()
        self.donor = Donor.objects.create(
            name="Test Donor", donor_type="Blood", blood_type="O+", region="Accra", phone="1"
        )

    def make_appointment(self, **overrides):
        body = {
            "donorId": str(self.donor.id),
            "date": (date.today() + timedelta(days=1)).isoformat(),
            "time": "09:30",
            "site": "Ridge Mobile Unit",
            "purpose": "Blood donation",
        }
        body.update(overrides)
        return self.client.post("/api/appointments/", body, content_type="application/json")

    def test_create_appointment(self):
        response = self.make_appointment()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_rejects_missing_donor(self):
        response = self.make_appointment(donorId="999999")
        self.assertEqual(response.status_code, 400)
        self.assertIn("donorId", response.json()["errors"])

    def test_rejects_absent_donor_id(self):
        response = self.make_appointment(donorId="")
        self.assertEqual(response.status_code, 400)

    def test_rejects_past_date(self):
        response = self.make_appointment(date=(date.today() - timedelta(days=1)).isoformat())
        self.assertEqual(response.status_code, 400)
        self.assertIn("date", response.json()["errors"])

    def test_rejects_bad_time(self):
        response = self.make_appointment(time="25:99")
        self.assertEqual(response.status_code, 400)
        self.assertIn("time", response.json()["errors"])


class InventoryApiTests(AuthenticatedTestCase):
    def test_adjust_inventory(self):
        response = self.client.post(
            "/api/inventory/", {"blood_type": "O+", "delta": 3}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["inventory"]["O+"], 3)

    def test_inventory_never_negative(self):
        InventoryItem.objects.create(blood_type="A-", units=1)
        response = self.client.post(
            "/api/inventory/", {"blood_type": "A-", "delta": -5}, content_type="application/json"
        )
        self.assertEqual(response.json()["inventory"]["A-"], 0)

    def test_rejects_invalid_blood_type(self):
        response = self.client.post(
            "/api/inventory/", {"blood_type": "Z", "delta": 1}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_non_integer_delta(self):
        response = self.client.post(
            "/api/inventory/", {"blood_type": "O+", "delta": "many"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)


class AlertApiTests(AuthenticatedTestCase):
    def test_create_alert(self):
        response = self.client.post(
            "/api/alerts/",
            {"level": "Notice", "title": "Stock check", "message": "All good."},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

    def test_rejects_invalid_level(self):
        response = self.client.post(
            "/api/alerts/",
            {"level": "Panic", "title": "T", "message": "M"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class ResetApiTests(AuthenticatedTestCase):
    def test_reset_reseeds_demo_data(self):
        Donor.objects.create(name="X", donor_type="Blood", blood_type="O+", region="R", phone="1")
        response = self.client.post("/api/reset/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Donor.objects.filter(name="X").exists())
        self.assertTrue(Donor.objects.filter(name="Amina Mensah").exists())

    @override_settings(DEMO_MODE=False)
    def test_reset_forbidden_outside_demo_mode(self):
        RecipientCase.objects.create(
            recipient="Keep Me", need_type="Blood", priority="High",
            blood_type="O+", hospital="H", region="R",
        )
        response = self.client.post("/api/reset/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(RecipientCase.objects.filter(recipient="Keep Me").exists())


class CsrfTests(AuthenticatedTestCase):
    def test_post_without_csrf_is_rejected(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            "/api/alerts/",
            {"level": "Notice", "title": "T", "message": "M"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
