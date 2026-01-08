import unittest
from src.domain.services import AuditService
from src.domain.merkle import MerkleTree
from src.ports.common import SystemClockAdapter, UuidIdAdapter
from talos_sdk.adapters.hash import NativeHashAdapter
from talos_sdk.adapters.memory_store import InMemoryAuditStore


class TestProofVerification(unittest.TestCase):
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

    def verify_merkle_proof(self, root_hex: str, leaf_data: str, proof_hex_list: list) -> bool:
        """
        Independent implementation of Merkle proof verification.
        """
        self.hash_port.sha256(leaf_data.encode("utf-8"))

        # We need to know if we are left or right sibling at each step.
        # However, our simple tree duplicates last leaf if odd.
        # This makes proof verification tricky without index or side info.
        # In our implementation, we determine side by index % 2.
        # But wait, the proof list just contains siblings.
        # Let's see how MerkleTree handles it.
        # It uses: is_right_node = index % 2 == 1 -> sibling is index - 1.
        # So we need the original index to verify.

        # Let's simplified: If we don't have index, we'd have to try both sides
        # or have the proof include 'dir'.
        # Since our ProofView doesn't include 'dir', let's fix it or use a helper that knows the index.
        return False  # Placeholder for now, I'll update the logic below.

    def test_proof_integrity(self):
        # Ingest events and verify proofs for each
        ids = []
        for i in range(5):
            event = self.service.ingest_event("TEST")
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
