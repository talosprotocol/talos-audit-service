"""
Talos Audit Service - FastAPI Application
Provides REST API for audit log queries and analytics.
"""

from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import Optional
import time

from bootstrap import get_app_container
from talos_sdk.ports.audit_store import IAuditStorePort, TimeWindow


app = FastAPI(
    title="Talos Audit Service",
    description="Audit log query and analytics service",
    version="0.1.0",
)


class StatsResponse(BaseModel):
    """Response model for audit statistics."""

    count: int
    window_start: float
    window_end: float


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "audit-service", "timestamp": time.time()}


@app.get("/events")
def list_events(
    limit: int = Query(100, ge=1, le=1000),
    before: Optional[str] = None,
):
    """List audit events with pagination."""
    container = get_app_container()
    audit_store = container.resolve(IAuditStorePort)

    page = audit_store.list(before=before, limit=limit)

    return {
        "events": [
            {
                "event_id": getattr(e, "event_id", None),
                "timestamp": getattr(e, "timestamp", None),
                "event_type": getattr(e, "event_type", None),
            }
            for e in page.events
        ],
        "next_cursor": page.next_cursor,
        "count": len(page.events),
    }


@app.get("/stats", response_model=StatsResponse)
def get_stats(
    start: float = Query(..., description="Window start timestamp"),
    end: float = Query(..., description="Window end timestamp"),
):
    """Get audit event statistics for a time window."""
    container = get_app_container()
    audit_store = container.resolve(IAuditStorePort)

    window = TimeWindow(start=start, end=end)
    stats = audit_store.stats(window)

    return StatsResponse(
        count=stats.count,
        window_start=start,
        window_end=end,
    )
