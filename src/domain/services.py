from typing import Optional, Dict, Any
from src.domain.models import Event, RootView, ProofView
from src.domain.merkle import MerkleTree
from src.domain.errors import ValidationError, NotFoundError, ConflictError
from src.ports.common import IClockPort, IIdPort
from talos_sdk.ports.audit_store import IAuditStorePort

class AuditService:
    """
    Domain Service for Audit operations.
    Orchestrates Ports and Domain Entities/Logic.
    """

    def __init__(
        self,
        store: IAuditStorePort,
        merkle_tree: MerkleTree,
        clock: IClockPort,
        id_gen: IIdPort
    ):
        self._store = store
        self._merkle_tree = merkle_tree
        self._clock = clock
        self._id_gen = id_gen
        self._initialize_tree()

    def _initialize_tree(self):
        """Rebuild tree from store on startup."""
        page = self._store.list(limit=10000)
        for event in page.events:
            # We need to wrap store events into domain events if they differ,
            # but for now we assume they are compatible or we just need the IDs/data for the tree.
            # To be safe, we Re-wrap them to the Domain Model.
            domain_event = Event(
                event_id=getattr(event, 'event_id'),
                timestamp=getattr(event, 'timestamp'),
                event_type=getattr(event, 'event_type'),
                details=getattr(event, 'details', {})
            )
            self._merkle_tree.add_leaf(domain_event)

    def ingest_event(
        self,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None
    ) -> Event:
        """
        Ingest a new audit event.
        - Generates ID and Timestamp if not provided.
        - Enforces idempotency (optional, for now simple append).
        - Persists to Store.
        - Anchors to Merkle Tree.
        """
        if not event_type:
            raise ValidationError("event_type is required")

        actual_id = event_id or self._id_gen.generate_id()
        
        # Simple idempotency check if tree is rebuilt
        if self._merkle_tree.has_event(actual_id):
            # For this reference impl, we return existing if ID provided? 
            # Or raise Conflict. Let's raise Conflict if ID was explicit.
            if event_id:
                raise ConflictError(f"Event with id {event_id} already exists")
            # If generated ID collided (unlikely), regenerate or fail.
        
        event = Event(
            event_id=actual_id,
            timestamp=self._clock.now(),
            event_type=event_type,
            details=details or {}
        )

        # Persistence (Secondary Port)
        self._store.append(event)
        
        # Domain Logic (Merkle)
        self._merkle_tree.add_leaf(event)

        return event

    def get_root(self) -> RootView:
        return self._merkle_tree.get_root()

    def get_proof(self, event_id: str) -> ProofView:
        if not self._merkle_tree.has_event(event_id):
            raise NotFoundError(f"Event {event_id} not found")
        return self._merkle_tree.get_proof(event_id)
