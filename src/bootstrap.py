from src.domain.services import AuditService
from src.domain.merkle import MerkleTree
from src.ports.common import SystemClockAdapter, UuidIdAdapter
from talos_sdk.container import Container, get_container
from talos_sdk.ports.audit_store import IAuditStorePort
from talos_sdk.ports.hash import IHashPort
from talos_sdk.adapters.memory_store import InMemoryAuditStore
from talos_sdk.adapters.hash import NativeHashAdapter

_container = None


def bootstrap() -> Container:
    """Initialize the DI container (Composition Root)."""
    container = get_container()

    # Register Secondary Ports / Adapters (SDK)
    container.register(IAuditStorePort, InMemoryAuditStore())
    container.register(IHashPort, NativeHashAdapter())

    # Register Infrastructure Adapters (Internal)
    container.register(SystemClockAdapter, SystemClockAdapter())
    container.register(UuidIdAdapter, UuidIdAdapter())

    # Register Domain Logic
    hash_port = container.resolve(IHashPort)
    merkle_tree = MerkleTree(hash_port)
    container.register(MerkleTree, merkle_tree)

    # Register Domain Service
    audit_service = AuditService(
        store=container.resolve(IAuditStorePort),
        merkle_tree=merkle_tree,
        clock=container.resolve(SystemClockAdapter),
        id_gen=container.resolve(UuidIdAdapter),
    )
    container.register(AuditService, audit_service)

    return container


def get_app_container() -> Container:
    global _container
    if _container is None:
        _container = bootstrap()
    return _container


def get_audit_service() -> AuditService:
    """Direct accessor for FastAPI dependency injection."""
    return get_app_container().resolve(AuditService)
