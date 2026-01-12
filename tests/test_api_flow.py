import hashlib
import json
from fastapi.testclient import TestClient
from src.adapters.http.main import app
import unittest


def build_valid_event(event_id="e-1"):
    event = {
        "schema_id": "talos.audit_event",
        "schema_version": "v1",
        "event_id": event_id,
        "ts": "2026-01-11T18:23:45.123Z",
        "request_id": "req-1",
        "surface_id": "test.op",
        "outcome": "success",
        "principal": {"auth_mode": "bearer", "principal_id": "p-1", "team_id": "t-1"},
        "http": {"method": "GET", "path": "/v1/test", "status_code": 200},
        "meta": {},
        "resource": None,
    }
    # JCS
    canonical = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    event["event_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return event


class TestApiFlow(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_full_flow(self):
        # 1. Check initial root
        resp = self.client.get("/root")
        self.assertEqual(resp.status_code, 200)

        # 2. Add event 1
        payload = build_valid_event("e-1")
        resp = self.client.post("/events", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        event_id_1 = data["event_id"]
        self.assertEqual(event_id_1, "e-1")

        # 3. Add event 2
        payload2 = build_valid_event("e-2")
        resp = self.client.post("/events", json=payload2)
        self.assertEqual(resp.status_code, 200)
        event_id_2 = resp.json()["event_id"]
        self.assertEqual(event_id_2, "e-2")

        # 4. Check Root
        resp = self.client.get("/root")
        self.assertEqual(resp.status_code, 200)
        root = resp.json()["root"]
        self.assertNotEqual(root, "")

        # 5. Get Proof for Event 1
        resp = self.client.get(f"/proof/{event_id_1}")
        self.assertEqual(resp.status_code, 200)
        path = resp.json()["path"]
        self.assertTrue(len(path) > 0)

        # 6. Verify Reject Invalid Hash
        payload3 = build_valid_event("e-3")
        payload3["event_hash"] = "invalid"
        resp = self.client.post("/events", json=payload3)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("hash mismatch", resp.json()["detail"].lower())
