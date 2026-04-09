import unittest
from src.domain.services import AuditService
from src.domain.merkle import MerkleTree
from src.domain.models import Event
from src.ports.common import SystemClockAdapter, UuidIdAdapter
from talos_sdk.adapters.hash import NativeHashAdapter
from talos_sdk.adapters.memory_store import InMemoryAuditStore
import hashlib


class TestProofVerification(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.hash_port = NativeHashAdapter()
        self.store = InMemoryAuditStore()
        self.merkle_tree = MerkleTree(self.hash_port)
        self.service = AuditService(
            store=self.store,
            merkle_tree=self.merkle_tree,
            clock=SystemClockAdapter(),
            id_gen=UuidIdAdapter(),
        )

    async def test_proof_integrity(self):
        # Ingest events and verify proofs for each
        ids = []
        for i in range(5):
            e = Event(
                schema_id="talos.audit_event",
                schema_version="v1",
                event_id=f"e-{i}",
                ts="2026-01-11T18:23:45.123Z",
                request_id=f"req-{i}",
                surface_id="test.op",
                outcome="success",
                principal={"auth_mode": "bearer", "principal_id": f"p-{i}", "team_id": "t-1"},
                http={"method": "GET", "path": "/v1/test", "status_code": 200},
                meta={},
                resource=None,
                event_hash="",
            )
            canonical = str(e)
            e = e.model_copy(
                update={"event_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}
            )
            event = await self.service.ingest_event(e)
            ids.append((event.event_id, str(event)))

        root = self.service.get_root().root

        for event_id, event_str in ids:
            proof_view = self.service.get_proof(event_id)
            path = proof_view.path

            calculated_hash = self.hash_port.sha256(event_str.encode("utf-8"))

            for step in path:
                sibling = bytes.fromhex(step.hash)
                if step.position == "right":
                    # We are left
                    combined = calculated_hash + sibling
                else:
                    # We are right
                    combined = sibling + calculated_hash

                calculated_hash = self.hash_port.sha256(combined)

            self.assertEqual(calculated_hash.hex(), root, f"Proof failed for {event_id}")


if __name__ == "__main__":
    unittest.main()
