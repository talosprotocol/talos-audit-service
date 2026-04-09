import pytest
from unittest.mock import MagicMock
from src.domain.merkle import MerkleTree
from src.domain.hardening import AuditHardeningSink, HardeningError
from src.domain.models import Event


@pytest.fixture
def hash_port():
    import hashlib

    port = MagicMock()
    port.sha256 = lambda d: hashlib.sha256(d).digest()
    return port


@pytest.mark.asyncio
async def test_hardening_verify_integrity(hash_port):
    tree = MerkleTree(hash_port)

    # Add some events
    event1 = Event(
        event_id="e1",
        ts="1",
        request_id="r1",
        surface_id="s1",
        outcome="OK",
        principal={},
        http={},
        meta={},
        event_hash="h1",
    )
    event2 = Event(
        event_id="e2",
        ts="2",
        request_id="r2",
        surface_id="s2",
        outcome="OK",
        principal={},
        http={},
        meta={},
        event_hash="h2",
    )
    tree.add_leaf(event1)
    tree.add_leaf(event2)

    sink = AuditHardeningSink(tree)

    # Normal case
    assert await sink.verify_tree_integrity() is True


@pytest.mark.asyncio
async def test_hardening_detect_tampering(hash_port):
    tree = MerkleTree(hash_port)
    event1 = Event(
        event_id="e1",
        ts="1",
        request_id="r1",
        surface_id="s1",
        outcome="OK",
        principal={},
        http={},
        meta={},
        event_hash="h1",
    )
    tree.add_leaf(event1)

    sink = AuditHardeningSink(tree)
    await sink.verify_tree_integrity()

    # Tamper with internal tree state
    tree._tree[-1] = [b"tampered"]

    with pytest.raises(HardeningError):
        await sink.verify_tree_integrity()


@pytest.mark.asyncio
async def test_hardening_snapshot_with_signature(hash_port):
    tree = MerkleTree(hash_port)
    tree.add_leaf(
        Event(
            event_id="e1",
            ts="1",
            request_id="r1",
            surface_id="s1",
            outcome="OK",
            principal={},
            http={},
            meta={},
            event_hash="h1",
        )
    )

    signer = MagicMock()
    signer.sign.return_value = b"signature-123"

    sink = AuditHardeningSink(tree, signer)
    snapshot = await sink.create_integrity_snapshot()

    assert snapshot["verified"] is True
    assert snapshot["signature"] == b"signature-123".hex()
    signer.sign.assert_called_once()
