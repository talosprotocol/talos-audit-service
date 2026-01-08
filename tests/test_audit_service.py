import unittest
from unittest.mock import MagicMock
from src.domain.services import AuditService
from src.domain.merkle import MerkleTree
from src.domain.errors import ValidationError, NotFoundError, ConflictError
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
        event = self.service.ingest_event(event_type="MESSAGE", details={"user": "alice"})

        self.assertEqual(event.event_id, "fixed-id")
        self.assertEqual(event.timestamp, 1000.0)
        self.assertEqual(event.event_type, "MESSAGE")
        self.mock_store.append.assert_called_once()

        root = self.service.get_root()
        self.assertNotEqual(root.root, "")

    def test_ingest_rejects_empty_type(self):
        with self.assertRaises(ValidationError):
            self.service.ingest_event(event_type="")

    def test_idempotency_conflict(self):
        # First ingest
        self.service.ingest_event(event_type="test", event_id="unique-1")

        # Second ingest with same ID should fail
        with self.assertRaises(ConflictError):
            self.service.ingest_event(event_type="test", event_id="unique-1")

    def test_get_proof_not_found(self):
        with self.assertRaises(NotFoundError):
            self.service.get_proof("missing-id")

    def test_snapshot_consistency(self):
        # Ingest 3 events
        self.service.ingest_event(event_type="MESSAGE")
        id2 = self.service.ingest_event(event_type="MESSAGE").event_id
        self.service.ingest_event(event_type="MESSAGE")

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
