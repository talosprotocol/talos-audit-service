from typing import List, Dict
from talos_sdk.ports.hash import IHashPort
from src.domain.models import Event, RootView, ProofView


class MerkleTree:
    """
    A pure domain implementation of a Merkle Tree.
    Does not depend on any external I/O or frameworks.
    """

    def __init__(self, hash_port: IHashPort):
        self._hash_port = hash_port
        self._leaves: List[bytes] = []
        self._event_id_to_index: Dict[str, int] = {}

    def add_leaf(self, event: Event) -> int:
        """Add an event to the tree and return its index."""
        data_bytes = str(event).encode("utf-8")
        leaf_hash = self._hash_port.sha256(data_bytes)

        index = len(self._leaves)
        self._leaves.append(leaf_hash)
        self._event_id_to_index[event.event_id] = index
        return index

    def get_root(self) -> RootView:
        """Calculate and return the Merkle Root."""
        if not self._leaves:
            return RootView(root="")

        root_bytes = self._compute_root(self._leaves)
        return RootView(root=root_bytes.hex())

    def _compute_root(self, nodes: List[bytes]) -> bytes:
        if len(nodes) == 1:
            return nodes[0]

        new_level = []
        for i in range(0, len(nodes), 2):
            left = nodes[i]
            right = nodes[i + 1] if i + 1 < len(nodes) else left
            combined = left + right
            new_level.append(self._hash_port.sha256(combined))

        return self._compute_root(new_level)

    def get_proof(self, event_id: str) -> ProofView:
        """Generate Merkle Proof for an event."""
        if event_id not in self._event_id_to_index:
            return ProofView(event_id=event_id, proof=[])

        index = self._event_id_to_index[event_id]
        proof_hashes = []
        current_level = list(self._leaves)

        while len(current_level) > 1:
            if len(current_level) % 2 == 1:
                current_level.append(current_level[-1])

            is_right_node = index % 2 == 1
            sibling_index = index - 1 if is_right_node else index + 1

            proof_hashes.append(current_level[sibling_index].hex())

            new_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1]
                new_level.append(self._hash_port.sha256(left + right))

            current_level = new_level
            index //= 2

        return ProofView(event_id=event_id, proof=proof_hashes)

    def has_event(self, event_id: str) -> bool:
        return event_id in self._event_id_to_index
