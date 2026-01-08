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
        event = Event(event_id="evt1", timestamp=0.0, event_type="test", details={"data": "data1"})
        # Note: Event __str__ uses event_id, timestamp, type, details.
        # So we need to match our mock expectations or just accept what it produces.

        tree.add_leaf(event)
        self.assertEqual(
            tree.get_root().root, self.mock_hash.sha256(str(event).encode("utf-8")).hex()
        )

    def test_simple_string_events(self):
        tree = MerkleTree(self.mock_hash)

        e1 = Event(event_id="1", timestamp=0.0, event_type="TEST", details={})
        e2 = Event(event_id="2", timestamp=0.0, event_type="TEST", details={})

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

        events = ["e1", "e2", "e3", "e4"]
        event_objs = []
        for i, e in enumerate(events):
            obj = Event(event_id=f"id_{i}", timestamp=0.0, event_type="TEST", details={"d": e})
            event_objs.append(obj)
            tree.add_leaf(obj)

        # Tree:
        #       Root
        #    H12    H34
        #  H1  H2  H3  H4

        # H1 = hash(e1)
        # H2 = hash(e2)
        # H12 = hash(H1+H2)

        # Proof for e1 (index 0): [H2, H34]
        # Verify proof locally in test

        proof = tree.get_proof("id_0").path
        self.assertEqual(len(proof), 2)
        self.mock_hash.sha256(str(event_objs[0]).encode("utf-8"))
        h2 = self.mock_hash.sha256(str(event_objs[1]).encode("utf-8"))
        h3 = self.mock_hash.sha256(str(event_objs[2]).encode("utf-8"))
        h4 = self.mock_hash.sha256(str(event_objs[3]).encode("utf-8"))

        self.assertEqual(proof[0].hash, h2.hex())
        self.assertEqual(proof[0].position, "right")
        self.assertEqual(proof[1].hash, self.mock_hash.sha256(h3 + h4).hex())
        self.assertEqual(proof[1].position, "right")


if __name__ == "__main__":
    unittest.main()
