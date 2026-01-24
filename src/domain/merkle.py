from typing import List, Dict, Any
from talos_sdk.ports.hash import IHashPort
from src.domain.models import Event, RootView, ProofView, ProofStep


class MerkleTree:
    """
    A pure domain implementation of a Merkle Tree.
    Stores levels for fast proof generation.
    """

    def __init__(self, hash_port: IHashPort):
        self._hash_port = hash_port
        self._leaves: List[bytes] = []
        self._tree: List[List[bytes]] = []
        self._event_id_to_index: Dict[str, int] = {}

    def add_leaf(self, event: Event) -> int:
        """Add an event to the tree and return its index."""
        data_bytes = str(event).encode("utf-8")
        leaf_hash = self._hash_port.sha256(data_bytes)

        index = len(self._leaves)
        self._leaves.append(leaf_hash)
        self._event_id_to_index[event.event_id] = index
        self._rebuild()
        return index

    def initialize_from_events(self, events: List[Any]):
        """Efficiently initialize tree from a list of historical events."""
        self._leaves = []
        self._event_id_to_index = {}
        
        for i, event in enumerate(events):
            # Re-wrap if it's a DB row object
            if not isinstance(event, Event):
                # Minimal hydration for hashing
                from src.domain.models import Event as DomainEvent
                hydrate = DomainEvent(
                    schema_id=getattr(event, "schema_id", "talos.audit_event"),
                    schema_version=getattr(event, "schema_version", "v1"),
                    event_id=getattr(event, "event_id"),
                    ts=getattr(event, "ts", "0"),
                    request_id=getattr(event, "request_id", "0"),
                    surface_id=getattr(event, "surface_id", "n/a"),
                    outcome=getattr(event, "outcome", "OK"),
                    principal=getattr(event, "principal", {}),
                    http=getattr(event, "http", {}),
                    meta=getattr(event, "meta", {}),
                    resource=getattr(event, "resource", None),
                    event_hash=getattr(event, "event_hash", ""),
                )
                data_bytes = str(hydrate).encode("utf-8")
            else:
                data_bytes = str(event).encode("utf-8")
                
            leaf_hash = self._hash_port.sha256(data_bytes)
            self._leaves.append(leaf_hash)
            self._event_id_to_index[getattr(event, "event_id")] = i
            
        self._rebuild()

    def _rebuild(self):
        """Build the full tree levels from leaves."""
        if not self._leaves:
            self._tree = []
            return

        current_level = self._leaves
        self._tree = [current_level]

        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                combined = left + right
                next_level.append(self._hash_port.sha256(combined))
            current_level = next_level
            self._tree.append(current_level)

    def get_root(self) -> RootView:
        """Return the Merkle Root."""
        if not self._tree:
            return RootView(root="")
        return RootView(root=self._tree[-1][0].hex())

    def get_proof(self, event_id: str) -> ProofView:
        """Generate Merkle Proof for an event matching Wiki spec."""
        if event_id not in self._event_id_to_index:
            # This should ideally be handled by service
            return ProofView(event_id=event_id, entry_hash="", root="", height=0, path=[], index=-1)

        index = self._event_id_to_index[event_id]
        entry_hash = self._leaves[index].hex()
        path = []

        current_index = index
        for level_index in range(len(self._tree) - 1):
            level = self._tree[level_index]
            is_right = current_index % 2 == 1
            sibling_index = current_index - 1 if is_right else current_index + 1

            # handle odd node at end
            if sibling_index >= len(level):
                sibling_index = current_index

            path.append(
                ProofStep(position="left" if is_right else "right", hash=level[sibling_index].hex())
            )
            current_index //= 2

        return ProofView(
            event_id=event_id,
            entry_hash=entry_hash,
            root=self.get_root().root,
            height=len(self._tree),
            path=path,
            index=index,
        )

    def has_event(self, event_id: str) -> bool:
        return event_id in self._event_id_to_index
