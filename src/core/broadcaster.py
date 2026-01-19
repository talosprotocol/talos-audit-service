import asyncio
import logging
from typing import AsyncGenerator, List
from src.domain.models import Event

logger = logging.getLogger(__name__)

class EventBroadcaster:
    """
    Manages SSE subscriptions and broadcasts events to all connected clients.
    
    Thread-safe with bounded queues to prevent memory exhaustion.
    Designed for single-replica deployment (v1). For multi-replica,
    replace with Redis PubSub or equivalent.
    """
    def __init__(self, max_queue_size: int = 100):
        self._subscribers: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()  # Concurrency safety
        self._max_queue_size = max_queue_size

    async def subscribe(self) -> AsyncGenerator[Event, None]:
        """
        Subscribe to the event stream. Yields events as they are broadcast.
        """
        # Bounded queue for backpressure
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue_size)
        
        async with self._lock:
            self._subscribers.append(queue)
        
        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            # Client disconnected - cleanup
            async with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)
            raise
        finally:
            # Ensure cleanup even if exception not CancelledError
            async with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    async def publish(self, event: Event) -> None:
        """
        Broadcast an event to all active subscribers.
        
        Uses snapshot of subscribers to avoid race conditions during iteration.
        Drops events for slow consumers (queue full).
        """
        async with self._lock:
            # Snapshot to avoid mutation during iteration
            subscribers = list(self._subscribers)
        
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop event for slow consumer (backpressure policy)
                logger.warning(f"Subscriber queue full (size={self._max_queue_size}), dropping event")
