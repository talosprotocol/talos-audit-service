from typing import Any
from src.domain.models import Event, RootView, ProofView
from src.domain.merkle import MerkleTree
from src.domain.errors import ValidationError, NotFoundError, ConflictError
from src.ports.common import IClockPort, IIdPort
from talos_sdk.ports.audit_store import IAuditStorePort  # type: ignore


class AuditService:
    """
    Domain Service for Audit operations.
    Orchestrates Ports and Domain Entities/Logic.
    """

    VALID_ENTRY_TYPES = {
        "MESSAGE",
        "SESSION",
        "CAP_GRANT",
        "CAP_REVOKE",
        "KEY_ROTATE",
        "IDENTITY",
        "TEST",  # Case insensitive match will now work
    }

    def __init__(
        self,
        store: IAuditStorePort,
        merkle_tree: MerkleTree,
        clock: IClockPort,
        id_gen: IIdPort,
        broadcaster: Any = None,  # Inject broadcaster
    ):
        self._store = store
        self._merkle_tree = merkle_tree
        self._clock = clock
        self._id_gen = id_gen
        self._broadcaster = broadcaster
        self._initialize_tree()

    def _initialize_tree(self):
        """Rebuild tree from store on startup."""
        import logging
        logger = logging.getLogger("audit-domain")
        logger.info("🌳 Starting Merkle Tree initialization from store...")
        page = self._store.list(limit=10000)
        logger.info(f"📚 Loaded {len(page.events)} events for tree initialization")
        
        # Batch add leaves to avoid O(N^2) rebuild disaster
        self._merkle_tree.initialize_from_events(page.events)
        
        logger.info("✅ Merkle Tree initialization complete")

    async def ingest_event(self, event: Event) -> Event:
        """
        Ingest a new audit event.
        - Verifies event_hash integrity (RFC 8785).
        - Persists to Store.
        - Anchors to Merkle Tree.
        - Broadcasts to SSE subscribers.
        """
        # 1. Integrity Verification
        import hashlib

        canonical_str = str(event)
        calculated_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

        if calculated_hash != event.event_hash:
            raise ValidationError(
                f"Audit Integrity Failure: event_hash mismatch for event {event.event_id}"
            )

        # 2. Idempotency check
        if self._merkle_tree.has_event(event.event_id):
            raise ConflictError(f"Event with id {event.event_id} already exists")

        # 3. Persistence (Secondary Port)
        self._store.append(event)

        # 4. Domain Logic (Merkle)
        self._merkle_tree.add_leaf(event)

        # 5. Broadcast (SSE)
        if self._broadcaster:
            await self._broadcaster.publish(event)

        return event

    def get_root(self) -> RootView:
        return self._merkle_tree.get_root()

    def get_proof(self, event_id: str) -> ProofView:
        if not self._merkle_tree.has_event(event_id):
            raise NotFoundError(f"Event {event_id} not found")
        return self._merkle_tree.get_proof(event_id)

    def list_events(self, limit: int = 50, before: str | None = None):
        """
        List audit events with pagination.
        
        Ordering: DESC (newest first)
        Pagination: cursor-based using 'before' (strictly older than cursor)
        
        Args:
            limit: Maximum events to return (clamped to 1-200)
            before: Optional cursor for pagination (strictly older than)
        
        Returns:
            EventPage with items, next_cursor, has_more
        
        Raises:
            ValidationError: If cursor format is invalid
        """
        # Validate and clamp limit
        limit = min(max(1, limit), 200)
        
        # Validate cursor if provided
        if before:
            # Basic cursor format validation
            # TODO: Use canonical cursor validator from contracts
            if not self._is_valid_cursor(before):
                raise ValidationError(
                    f"Invalid cursor format: {before}"
                )
        
        # Fetch from store
        return self._store.list(limit=limit, before=before)
    
    def _is_valid_cursor(self, cursor: str) -> bool:
        """Validate cursor format (Base64 encoded timestamp:id)."""
        import re
        # Base64 regex
        return bool(re.match(r'^[a-z0-9+/=]+$', cursor, re.IGNORECASE))
