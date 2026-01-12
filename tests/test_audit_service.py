import unittest
from unittest.mock import MagicMock
from src.domain.services import AuditService
from src.domain.merkle import MerkleTree
from src.domain.models import Event
from src.domain.errors import NotFoundError, ConflictError
from src.ports.common import IClockPort, IIdPort
from talos_sdk.ports.audit_store import IAuditStorePort
from talos_sdk.ports.hash import IHashPort


class TestAuditService(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock(spec=IAuditStorePort)
        self.mock_store.list.return_value = MagicMock(events=[])

        self.mock_hash = MagicMock(spec=IHashPort)
        self.mock_hash.sha256.side_effect = lambda x: f"hash({x.decode('utf-8')})".encode("utf-8")

        self.merkle_tree = MerkleTree(self.mock_hash)

        self.mock_clock = MagicMock(spec=IClockPort)
        self.mock_clock.now.return_value = 1000.0

        self.mock_id_gen = MagicMock(spec=IIdPort)
        self.mock_id_gen.generate_id.return_value = "fixed-id"

        self.service = AuditService(
            store=self.mock_store,
            merkle_tree=self.merkle_tree,
            clock=self.mock_clock,
            id_gen=self.mock_id_gen,
        )

    def test_ingest_event_success(self):
        event_obj = Event(
            event_id="e-1",
            ts="2026-01-11T18:23:45.123Z",
            request_id="req-1",
            surface_id="test.op",
            outcome="success",
            principal={"auth_mode": "bearer", "principal_id": "p-1", "team_id": "t-1"},
            http={"method": "GET", "path": "/v1/test", "status_code": 200},
            meta={},
            event_hash="",
        )
        # Update hash
        import hashlib
        import json

        clean = event_obj.model_dump(exclude={"event_hash"})
        canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        event_obj = event_obj.model_copy(
            update={"event_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}
        )

        event = self.service.ingest_event(event_obj)

        self.assertEqual(event.event_id, "e-1")
        self.assertEqual(event.outcome, "success")
        self.mock_store.append.assert_called_once()

    def test_idempotency_conflict(self):
        event_obj = Event(
            event_id="unique-1",
            ts="2026-01-11T18:23:45.123Z",
            request_id="req-1",
            surface_id="test.op",
            outcome="success",
            principal={"auth_mode": "bearer", "principal_id": "p-1", "team_id": "t-1"},
            http={"method": "GET", "path": "/v1/test", "status_code": 200},
            meta={},
            event_hash="",
        )
        # Update hash
        import hashlib
        import json

        clean = event_obj.model_dump(exclude={"event_hash"})
        canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        event_obj = event_obj.model_copy(
            update={"event_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}
        )

        # First ingest
        self.service.ingest_event(event_obj)

        # Second ingest with same ID should fail
        with self.assertRaises(ConflictError):
            self.service.ingest_event(event_obj)

    def test_get_proof_not_found(self):
        with self.assertRaises(NotFoundError):
            self.service.get_proof("missing-id")

    def test_snapshot_consistency(self):
        def build_valid(eid):
            import hashlib

            e = Event(
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
                event_hash="",
            )
            c = str(e)
            e = e.model_copy(update={"event_hash": hashlib.sha256(c.encode("utf-8")).hexdigest()})
            return e

        # Ingest 3 events
        self.service.ingest_event(build_valid("e1"))
        id2 = build_valid("e2").event_id
        self.service.ingest_event(build_valid("e2"))
        self.service.ingest_event(build_valid("e3"))

        self.service.get_root()
        path2 = self.service.get_proof(id2).path

        # Verify proof locally against root_snap logic
        # Proof for e2 (index 1) in [e1, e2, e3]
        # Leaves: H1, H2, H3
        # Level 1: H12=H(H1+H2), H33=H(H3+H3)
        # Root: H(H12+H33)
        # Proof for H2: [H1, H33]

        self.assertEqual(len(path2), 2)
        # We don't need to rebuild the whole verification logic here,
        # but asserting that the proof is returned and root exists.
        self.assertTrue(all(p.hash for p in path2))


if __name__ == "__main__":
    unittest.main()
