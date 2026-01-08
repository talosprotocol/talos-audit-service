import unittest
from fastapi.testclient import TestClient
from src.adapters.http.main import app


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_create_event_invalid_json(self):
        # Missing event_type
        resp = self.client.post("/events", json={"details": {}})
        self.assertEqual(resp.status_code, 422)  # Unprocessable Entity (Pydantic validation)

    def test_create_event_wrong_type(self):
        # event_type should be string
        resp = self.client.post("/events", json={"event_type": 123})
        self.assertEqual(resp.status_code, 422)
        # Pydantic might coerce 123 to "123", let's try something non-coercible if possible
        # but 422 is standard for Pydantic failures.

    def test_not_found_error_mapping(self):
        resp = self.client.get("/proof/non-existent-id")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    def test_conflict_error_mapping(self):
        # First one
        self.client.post("/events", json={"event_type": "TEST", "event_id": "dup-1"})
        # Second one with same ID
        resp = self.client.post("/events", json={"event_type": "TEST", "event_id": "dup-1"})
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already exists", resp.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
