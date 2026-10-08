"""
Tests for WinterRoad Citizen and Admin Role-Based Access Control & Security
Verifies:
  1. Unauthenticated access to admin endpoints returns 401.
  2. Invalid auth token returns 401.
  3. Valid admin login returns access token with role 'admin'.
  4. Authenticated admin access succeeds on protected endpoints.
  5. Citizen tracking endpoint works publicly and strictly redacts private/admin data.
  6. Public verified-potholes endpoint returns only verified defects without leaking private fields.
"""
import unittest
from fastapi.testclient import TestClient
from backend.main import app, ADMIN_USERNAME, ADMIN_PASSWORD_ENV

class TestAuthAndRoles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_admin_endpoints_require_auth(self):
        """Unauthenticated requests must receive 401 on all protected admin endpoints."""
        protected_endpoints = [
            ("GET", "/api/reports"),
            ("GET", "/api/reports/1"),
            ("POST", "/api/reports/1/status", {"status": "verified"}),
            ("POST", "/api/plan", {"budget": 500000.0}),
            ("POST", "/api/reset", {}),
            ("DELETE", "/api/segments/SEG-01"),
            ("GET", "/api/reports.csv"),
            ("GET", "/api/admin/metrics"),
        ]

        for method, url, *body in protected_endpoints:
            with self.subTest(endpoint=f"{method} {url}"):
                if method == "GET":
                    resp = self.client.get(url)
                elif method == "DELETE":
                    resp = self.client.delete(url)
                elif method == "POST":
                    resp = self.client.post(url, json=body[0] if body else {})
                self.assertEqual(
                    resp.status_code, 401,
                    f"Expected 401 for unauthenticated {method} {url}, got {resp.status_code}"
                )

    def test_invalid_token_rejected(self):
        """Requests with forged or invalid bearer tokens must receive 401."""
        headers = {"Authorization": "Bearer invalid_token_12345"}
        resp = self.client.get("/api/reports", headers=headers)
        self.assertEqual(resp.status_code, 401)

    def test_admin_login_and_authenticated_access(self):
        """Admin can log in with configured credentials and access protected routes."""
        # 1. Invalid login fails
        bad_login = self.client.post("/api/auth/login", json={"username": ADMIN_USERNAME, "password": "wrong_password"})
        self.assertEqual(bad_login.status_code, 401)

        # 2. Valid login succeeds
        login_resp = self.client.post(
            "/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD_ENV}
        )
        self.assertEqual(login_resp.status_code, 200)
        data = login_resp.json()
        self.assertTrue(data["authenticated"])
        self.assertEqual(data["role"], "admin")
        token = data["access_token"]
        self.assertTrue(len(token) > 16)

        headers = {"Authorization": f"Bearer {token}"}

        # 3. Check /api/auth/me
        me_resp = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["role"], "admin")

        # 4. Check protected routes with valid token
        reports_resp = self.client.get("/api/reports", headers=headers)
        self.assertEqual(reports_resp.status_code, 200)
        self.assertIn("reports", reports_resp.json())

        plan_resp = self.client.post("/api/plan", json={"budget": 500000.0}, headers=headers)
        self.assertEqual(plan_resp.status_code, 200)
        self.assertIn("plan", plan_resp.json())

        metrics_resp = self.client.get("/api/admin/metrics", headers=headers)
        self.assertEqual(metrics_resp.status_code, 200)

    def test_public_citizen_endpoints(self):
        """Citizen endpoints must be publicly accessible without authentication."""
        # Health
        resp_h = self.client.get("/api/health")
        self.assertEqual(resp_h.status_code, 200)
        self.assertEqual(resp_h.json()["project"], "WinterRoad")

        # Config
        resp_c = self.client.get("/api/config")
        self.assertEqual(resp_c.status_code, 200)

        # Verified potholes public map
        resp_p = self.client.get("/api/citizen/verified-potholes")
        self.assertEqual(resp_p.status_code, 200)
        p_data = resp_p.json()
        self.assertIn("counters", p_data)
        self.assertIn("verified_potholes", p_data)
        for defect in p_data["verified_potholes"]:
            # Ensure no private citizen fields are leaked
            self.assertNotIn("photo_file", defect)
            self.assertNotIn("photo_url", defect)
            self.assertNotIn("annotated_file", defect)
            self.assertNotIn("admin_notes", defect)
            self.assertNotIn("note", defect)

    def test_citizen_tracking_redaction(self):
        """Ticket tracking must return progress without exposing admin or private data."""
        # 1. Login as admin to find an existing ticket code
        login_resp = self.client.post(
            "/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD_ENV}
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        rep_resp = self.client.get("/api/reports", headers=headers)
        reports = rep_resp.json().get("reports", [])

        if reports:
            sample_code = reports[0]["ticket_code"]
            # Look up ticket as anonymous citizen
            track_resp = self.client.get(f"/api/citizen/track/{sample_code}")
            self.assertEqual(track_resp.status_code, 200)
            data = track_resp.json()

            # Required public tracking fields
            self.assertEqual(data["ticket_code"], sample_code)
            self.assertIn("status", data)
            self.assertIn("status_step", data)
            self.assertIn("status_label", data)
            self.assertIn("status_description", data)

            # Strict privacy check: must NOT leak internal admin/server fields
            self.assertNotIn("photo_file", data)
            self.assertNotIn("photo_url", data)
            self.assertNotIn("annotated_file", data)
            self.assertNotIn("admin_notes", data)
            self.assertNotIn("mismatch_distance_m", data)
            self.assertNotIn("detections", data)

if __name__ == "__main__":
    unittest.main()
