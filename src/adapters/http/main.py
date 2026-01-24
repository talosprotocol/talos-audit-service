from fastapi import FastAPI, HTTPException, Depends, Request
import time
import json
import asyncio
from sse_starlette.sse import EventSourceResponse

from src.domain.services import AuditService
from src.domain.models import Event, RootView, ProofView
from src.domain.errors import DomainError, ValidationError, NotFoundError, ConflictError
from src.bootstrap import get_audit_service, get_broadcaster
from src.core.broadcaster import EventBroadcaster


app = FastAPI(
    title="Talos Audit Service",
    description="Pydantic-first Audit log query and analytics service",
    version="0.3.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "audit-service", "timestamp": time.time()}


@app.get("/version")
def version():
    """Version information"""
    return {
        "version": app.version,
        "git_sha": "unknown",
        "service": "audit-service"
    }


@app.post("/events")
async def create_event(event: Event, service: AuditService = Depends(get_audit_service)):
    try:
        return await service.ingest_event(event)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/events")
async def list_events(
    limit: int = 50,
    before: str | None = None,
    service: AuditService = Depends(get_audit_service)
):
    """
    Paginated JSON list of audit events.
    
    Ordering: DESC (newest first)
    Pagination: cursor-based, 'before' means strictly older than cursor
    
    Query params:
        limit: Max events to return (default 50, max 200)
        before: Optional cursor for pagination
    
    Returns:
        {
            "items": [AuditEvent, ...],
            "next_cursor": "string|null",
            "has_more": bool
        }
    
    Errors:
        400: Invalid cursor format (TALOS_INVALID_CURSOR)
    """
    try:
        page = service.list_events(limit=limit, before=before)
        
        # Convert events to dict
        items = [
            event.model_dump() if hasattr(event, "model_dump") else event.dict()
            for event in page.events
        ]
        
        # Stable response shape - always include all keys
        return {
            "items": items,
            "next_cursor": getattr(page, "next_cursor", None),
            "has_more": getattr(page, "has_more", False)
        }
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "TALOS_INVALID_CURSOR",
                "message": str(e)
            }
        )


@app.get("/events")
async def stream_events(request: Request, broadcaster: EventBroadcaster = Depends(get_broadcaster)):
    """
    Stream audit events via SSE (Server-Sent Events).
    
    Spec-compliant implementation:
    - First event is always 'meta' with version and connected_at
    - Heartbeat every 30s with empty data payload  
    - Audit events as 'audit_event'
    - Errors as 'error' event followed by stream termination
    """
    async def event_generator():
        try:
            # 1. Send meta event (MUST be first)
            from datetime import datetime, timezone
            connected_at = datetime.now(timezone.utc).isoformat()
            yield {
                "event": "meta",
                "data": json.dumps({
                    "version": "1",
                    "connected_at": connected_at
                })
            }
            
            # 2. Stream events with heartbeat
            async for event in broadcaster.subscribe():
                # Convert Pydantic model to dict/json
                yield {
                    "event": "audit_event",
                    "data": event.model_dump_json() if hasattr(event, "model_dump_json") else event.json()
                }
                
        except asyncio.CancelledError:
            # Client disconnected - normal cleanup via cancellation
            pass
        except Exception as e:
            # Internal error - emit error event then close
            logger.error(f"SSE internal error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({
                    "code": "TALOS_SSE_INTERNAL",
                    "message": str(e)
                })
            }

    return EventSourceResponse(event_generator())


@app.get("/root", response_model=RootView)
def get_root(service: AuditService = Depends(get_audit_service)):
    return service.get_root()


@app.get("/proof/{event_id}", response_model=ProofView)
def get_proof(event_id: str, service: AuditService = Depends(get_audit_service)):
    try:
        return service.get_proof(event_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=500, detail=str(e))
