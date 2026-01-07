"""
SDK Integration Tests for talos-audit-service.

Verifies that:
1. DI container is properly bootstrapped
2. SDK ports (audit, hash) are correctly registered
3. Audit store operations work correctly
"""

import pytest
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Skip all tests if talos_sdk is not installed
import importlib.util

SDK_AVAILABLE = importlib.util.find_spec("talos_sdk") is not None

pytestmark = pytest.mark.skipif(not SDK_AVAILABLE, reason="talos_sdk not installed")


class TestBootstrap:
    """Test DI container bootstrap."""

    def test_get_app_container_returns_container(self):
        """Container is created on first call."""
        from src.bootstrap import get_app_container

        container = get_app_container()
        assert container is not None

    def test_container_singleton(self):
        """Same container instance is reused."""
        from src.bootstrap import get_app_container

        c1 = get_app_container()
        c2 = get_app_container()
        assert c1 is c2

    def test_audit_store_registered(self):
        """IAuditStorePort is registered."""
        from src.bootstrap import get_app_container
        from talos_sdk.ports.audit_store import IAuditStorePort

        container = get_app_container()
        audit_store = container.resolve(IAuditStorePort)
        assert audit_store is not None

    def test_hash_port_registered(self):
        """IHashPort is registered."""
        from src.bootstrap import get_app_container
        from talos_sdk.ports.hash import IHashPort

        container = get_app_container()
        hash_port = container.resolve(IHashPort)
        assert hash_port is not None


class TestAuditStore:
    """Test audit store operations."""

    def test_append_event(self):
        """Can append an event to the store."""
        from src.bootstrap import get_app_container
        from talos_sdk.ports.audit_store import IAuditStorePort

        container = get_app_container()
        store = container.resolve(IAuditStorePort)

        class TestEvent:
            event_id = "audit-test-001"
            timestamp = 1234567890.0
            event_type = "test"

        # Should not raise
        store.append(TestEvent())

    def test_list_events(self):
        """Can list events from the store."""
        from src.bootstrap import get_app_container
        from talos_sdk.ports.audit_store import IAuditStorePort

        container = get_app_container()
        store = container.resolve(IAuditStorePort)

        page = store.list(limit=50)
        assert hasattr(page, "events")
        assert isinstance(page.events, list)

    def test_list_with_cursor(self):
        """List supports cursor for pagination."""
        from src.bootstrap import get_app_container
        from talos_sdk.ports.audit_store import IAuditStorePort

        container = get_app_container()
        store = container.resolve(IAuditStorePort)

        # First page
        page1 = store.list(limit=5)

        # If there's a next cursor, we can fetch more
        if page1.next_cursor:
            page2 = store.list(limit=5, cursor=page1.next_cursor)
            assert isinstance(page2.events, list)


class TestHashPort:
    """Test hash port functionality."""

    def test_canonical_hash_deterministic(self):
        """Hash is deterministic for same input."""
        from src.bootstrap import get_app_container
        from talos_sdk.ports.hash import IHashPort

        container = get_app_container()
        hash_port = container.resolve(IHashPort)

        data = {"agent_id": "agent-001", "action": "read"}
        h1 = hash_port.canonical_hash(data)
        h2 = hash_port.canonical_hash(data)

        assert h1 == h2

    def test_canonical_hash_key_order_invariant(self):
        """Hash ignores key ordering."""
        from src.bootstrap import get_app_container
        from talos_sdk.ports.hash import IHashPort

        container = get_app_container()
        hash_port = container.resolve(IHashPort)

        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}

        assert hash_port.canonical_hash(data1) == hash_port.canonical_hash(data2)
