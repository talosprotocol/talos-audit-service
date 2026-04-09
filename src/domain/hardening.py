import logging
from typing import Optional, Dict, Any
from .merkle import MerkleTree

logger = logging.getLogger(__name__)


class HardeningError(Exception):
    """Integrity hardening error."""

    pass


class AuditHardeningSink:
    """
    Background worker logic for hardening audit logs.

    Responsibilities:
    - Periodic Merkle Tree integrity verification
    - Batch integrity snapshots
    - Signature generation for tree roots
    """

    def __init__(self, merkle_tree: MerkleTree, signer: Optional[Any] = None):
        self._tree = merkle_tree
        self._signer = signer
        self._last_verified_root: Optional[str] = None

    async def verify_tree_integrity(self) -> bool:
        """
        Full re-computation of the Merkle Tree to detect tampering.
        """
        logger.info("Starting background audit integrity verification...")

        current_root = self._tree.get_root().root
        if not current_root:
            return True  # Empty is valid

        # Trigger internal rebuild to be sure
        self._tree._rebuild()
        new_root = self._tree.get_root().root

        if current_root != new_root:
            logger.critical(f"INTEGRITY BREACH: Root mismatch! {current_root} != {new_root}")
            raise HardeningError(
                "Merkle tree integrity check failed - potential tampering detected"
            )

        self._last_verified_root = new_root
        logger.info(f"Audit integrity verified. Root: {new_root}")
        return True

    async def create_integrity_snapshot(self) -> Dict[str, Any]:
        """
        Creates a signed snapshot of the current audit state.
        """
        await self.verify_tree_integrity()

        root_view = self._tree.get_root()
        snapshot = {
            "root": root_view.root,
            "timestamp": "2026-01-01T00:00:00Z",  # Placeholder
            "verified": True,
        }

        if self._signer:
            # Sign the root for non-repudiation
            signature = self._signer.sign(root_view.root.encode())
            snapshot["signature"] = signature.hex()

        return snapshot
