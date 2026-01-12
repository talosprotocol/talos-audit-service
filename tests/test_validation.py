import unittest
from fastapi.testclient import TestClient
from src.adapters.http.main import app


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_create_event_invalid_json(self):
        # Missing required fields like schema_id, schema_version etc if Pydantic enforced
        # Actually Event model has defaults for schema fields, but event_id, ts, etc are required.
        resp = self.client.post("/events", json={"event_id": "e-1"})
        self.assertEqual(resp.status_code, 422)

    def test_conflict_error_mapping(self):
        def build_valid(eid):
            import hashlib
            import json

            e = {
                "schema_id": "talos.audit_event",
                "schema_version": "v1",
                "event_id": eid,
                "ts": "2026-01-11T18:23:45.123Z",
                "request_id": "req-1",
                "surface_id": "test.op",
                "outcome": "success",
                "principal": {"auth_mode": "bearer", "principal_id": "p-1", "team_id": "t-1"},
                "http": {"method": "GET", "path": "/v1/test", "status_code": 200},
                "meta": {},
                "resource": None,
            }
            c = json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            e["event_hash"] = hashlib.sha256(c.encode("utf-8")).hexdigest()
            return e

        payload = build_valid("dup-1")
        # First one
        self.client.post("/events", json=payload)
        # Second one with same ID
        resp = self.client.post("/events", json=payload)
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already exists", resp.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
