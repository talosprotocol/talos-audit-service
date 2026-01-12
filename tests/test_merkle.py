import unittest
from unittest.mock import MagicMock
from src.domain.merkle import MerkleTree
from src.domain.models import Event
from talos_sdk.ports.hash import IHashPort
from talos_sdk.ports.audit_store import IAuditStorePort


class TestMerkleTree(unittest.TestCase):
    def setUp(self):
        self.mock_hash = MagicMock(spec=IHashPort)
        # Mock sha256 to return b"hash(" + data + b")" for predictability
        self.mock_hash.sha256.side_effect = lambda x: f"hash({x.decode('utf-8')})".encode("utf-8")

        self.mock_store = MagicMock(spec=IAuditStorePort)
        # Mock list to return empty first
        self.mock_store.list.return_value = MagicMock(events=[])

    def test_empty_tree(self):
        tree = MerkleTree(self.mock_hash)
        self.assertEqual(tree.get_root().root, "")

    def test_single_leaf(self):
        tree = MerkleTree(self.mock_hash)
        event = Event(
            schema_id="talos.audit_event",
            schema_version="v1",
            event_id="evt1",
            ts="2026-01-11T18:23:45.123Z",
            request_id="req-1",
            surface_id="test.op",
            outcome="success",
            principal={"auth_mode": "bearer", "principal_id": "p-1", "team_id": "t-1"},
            http={"method": "GET", "path": "/v1/test", "status_code": 200},
            meta={},
            resource=None,
            event_hash="some-hash",
        )
        tree.add_leaf(event)
        self.assertEqual(
            tree.get_root().root, self.mock_hash.sha256(str(event).encode("utf-8")).hex()
        )

    def test_simple_string_events(self):
        tree = MerkleTree(self.mock_hash)

        def build_event(eid):
            return Event(
                schema_id="talos.audit_event",
                schema_version="v1",
                event_id=eid,
                ts="2026-01-11T18:23:45.123Z",
                request_id="req-1",
                surface_id="test.op",
                outcome="success",
                principal={"auth_mode": "bearer", "principal_id": "p-1", "team_id": "t-1"},
                http={"method": "GET", "path": "/v1/test", "status_code": 200},
                meta={},
                resource=None,
                event_hash="some-hash",
            )

        e1 = build_event("1")
        e2 = build_event("2")

        # Leaf 1
        tree.add_leaf(e1)
        self.assertEqual(tree.get_root().root, self.mock_hash.sha256(str(e1).encode("utf-8")).hex())

        # Leaf 2
        tree.add_leaf(e2)
        h1 = self.mock_hash.sha256(str(e1).encode("utf-8"))
        h2 = self.mock_hash.sha256(str(e2).encode("utf-8"))
        expected_root = self.mock_hash.sha256(h1 + h2).hex()
        self.assertEqual(tree.get_root().root, expected_root)

    def test_proof_verification(self):
        tree = MerkleTree(self.mock_hash)

        def build_event(eid):
            return Event(
                schema_id="talos.audit_event",
                schema_version="v1",
                event_id=eid,
                ts="2026-01-11T18:23:45.123Z",
                request_id="req-1",
                surface_id="test.op",
                outcome="success",
                principal={"auth_mode": "bearer", "principal_id": "p-1", "team_id": "t-1"},
                http={"method": "GET", "path": "/v1/test", "status_code": 200},
                meta={},
                resource=None,
                event_hash="some-hash",
            )

        events = ["id_0", "id_1", "id_2", "id_3"]
        event_objs = []
        for eid in events:
            obj = build_event(eid)
            event_objs.append(obj)
            tree.add_leaf(obj)

        proof = tree.get_proof("id_0").path
        self.assertEqual(len(proof), 2)

        h2 = self.mock_hash.sha256(str(event_objs[1]).encode("utf-8"))
        h3 = self.mock_hash.sha256(str(event_objs[2]).encode("utf-8"))
        h4 = self.mock_hash.sha256(str(event_objs[3]).encode("utf-8"))

        self.assertEqual(proof[0].hash, h2.hex())
        self.assertEqual(proof[0].position, "right")
        self.assertEqual(proof[1].hash, self.mock_hash.sha256(h3 + h4).hex())
        self.assertEqual(proof[1].position, "right")


if __name__ == "__main__":
    unittest.main()
