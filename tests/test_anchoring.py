import unittest
import hashlib
from src.domain.services import AuditService, AnchoringService
from src.domain.merkle import MerkleTree
from src.domain.models import Event
from src.ports.common import SystemClockAdapter, UuidIdAdapter
from talos_sdk.adapters.hash import NativeHashAdapter
from talos_sdk.adapters.memory_store import InMemoryAuditStore


class MockAnchoringPort:
    async def anchor_root(self, root: str, chain: str) -> str:
        return f"tx_{chain}_{root[:8]}"


class TestAnchoring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hash_port = NativeHashAdapter()
        self.store = InMemoryAuditStore()
        self.merkle_tree = MerkleTree(self.hash_port)
        self.clock = SystemClockAdapter()
        self.id_gen = UuidIdAdapter()

        self.audit_service = AuditService(
            store=self.store,
            merkle_tree=self.merkle_tree,
            clock=self.clock,
            id_gen=self.id_gen,
        )
        self.anchoring_port = MockAnchoringPort()
        self.anchoring_service = AnchoringService(
            audit_service=self.audit_service,
            anchor_port=self.anchoring_port,
            clock=self.clock,
            id_gen=self.id_gen,
        )

    async def test_anchoring_pipeline(self):
        # 1. Ingest an event
        e = Event(
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
        canonical = str(e)
        e = e.model_copy(
            update={"event_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}
        )
        await self.audit_service.ingest_event(e)

        # 2. Anchor the root
        anchor = await self.anchoring_service.anchor_current_root("ethereum")
        self.assertEqual(anchor.chain, "ethereum")
        self.assertIn("tx_ethereum_", anchor.tx_hash)

        # 3. Verify event against anchor
        verified = self.anchoring_service.verify_event_against_anchor("e-1", anchor.anchor_id)
        self.assertTrue(verified)

    async def test_invalid_anchor_verification(self):
        # Ingest event
        e = Event(
            event_id="e-2",
            ts="2026-01-11T18:23:45.123Z",
            request_id="req-2",
            surface_id="test.op",
            outcome="success",
            principal={"auth_mode": "bearer", "principal_id": "p-2", "team_id": "t-1"},
            http={"method": "GET", "path": "/v1/test", "status_code": 200},
            meta={},
            event_hash="",
        )
        canonical = str(e)
        e = e.model_copy(
            update={"event_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}
        )
        await self.audit_service.ingest_event(e)

        # Anchor
        anchor = await self.anchoring_service.anchor_current_root("solana")

        # Ingest another event (root changes)
        e3 = Event(
            event_id="e-3",
            ts="2026-01-11T18:23:45.123Z",
            request_id="req-3",
            surface_id="test.op",
            outcome="success",
            principal={"auth_mode": "bearer", "principal_id": "p-3", "team_id": "t-1"},
            http={"method": "GET", "path": "/v1/test", "status_code": 200},
            meta={},
            event_hash="",
        )
        canonical = str(e3)
        e3 = e3.model_copy(
            update={"event_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}
        )
        await self.audit_service.ingest_event(e3)

        # Verify e-3 against OLD anchor (should be false if it's not in that root)
        verified = self.anchoring_service.verify_event_against_anchor("e-3", anchor.anchor_id)
        self.assertFalse(verified)


if __name__ == "__main__":
    unittest.main()
