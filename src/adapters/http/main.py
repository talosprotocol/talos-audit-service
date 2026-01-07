from fastapi import FastAPI, HTTPException, Depends
from typing import Optional, Dict, Any
import time

from src.domain.services import AuditService
from src.domain.models import Event, RootView, ProofView
from src.domain.errors import DomainError, ValidationError, NotFoundError, ConflictError
from src.bootstrap import get_audit_service

from pydantic import BaseModel

class EventCreateRequest(BaseModel):
    event_type: str
    details: Optional[Dict[str, Any]] = None
    event_id: Optional[str] = None

app = FastAPI(
    title="Talos Audit Service",
    description="Pydantic-first Audit log query and analytics service",
    version="0.3.0",
)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "audit-service", "timestamp": time.time()}

@app.post("/events", response_model=Event)
def create_event(
    request: EventCreateRequest,
    service: AuditService = Depends(get_audit_service)
):
    try:
        event = service.ingest_event(
            event_type=request.event_type,
            details=request.details,
            event_id=request.event_id
        )
        return event
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/root", response_model=RootView)
def get_root(service: AuditService = Depends(get_audit_service)):
    return service.get_root()

@app.get("/proof/{event_id}", response_model=ProofView)
def get_proof(
    event_id: str,
    service: AuditService = Depends(get_audit_service)
):
    try:
        return service.get_proof(event_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=500, detail=str(e))
