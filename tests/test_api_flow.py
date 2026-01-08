from fastapi.testclient import TestClient
from src.adapters.http.main import app
import unittest


class TestApiFlow(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_full_flow(self):
        # 1. Check initial root (should be empty string if store empty)
        # Note: Depending on order of tests, store might not be empty if singleton persisted across tests?
        # InMemoryAuditStore likely created per process or singleton in bootstrap.
        # bootstrap.py:
        # _container = None, get_app_container() lazily creates it.
        # So likely shared if running multiple tests in same process.
        # But for this test file, valid.

        resp = self.client.get("/root")
        self.assertEqual(resp.status_code, 200)
        # initial_root = resp.json()["root"]

        # 2. Add event 1
        payload = {"event_type": "SESSION", "details": {"user": "alice"}}
        resp = self.client.post("/events", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        event_id_1 = data["event_id"]

        # 3. Add event 2
        resp = self.client.post("/events", json={"event_type": "SESSION"})
        self.assertEqual(resp.status_code, 200)
        event_id_2 = resp.json()["event_id"]

        # 4. Check Root
        resp = self.client.get("/root")
        self.assertEqual(resp.status_code, 200)
        root = resp.json()["root"]
        self.assertNotEqual(root, "")

        # 5. Get Proof for Event 1
        resp = self.client.get(f"/proof/{event_id_1}")
        self.assertEqual(resp.status_code, 200)
        path = resp.json()["path"]
        # With 2 leaves at least, path should not be empty
        self.assertTrue(len(path) > 0)

        # 6. Get Proof for Event 2
        resp = self.client.get(f"/proof/{event_id_2}")
        self.assertEqual(resp.status_code, 200)
        path = resp.json()["path"]
        self.assertTrue(len(path) > 0)


if __name__ == "__main__":
    unittest.main()
