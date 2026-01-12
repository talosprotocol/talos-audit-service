from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, List, Optional


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_id: str = "talos.audit_event"
    schema_version: str = "v1"
    event_id: str
    ts: str
    request_id: str
    surface_id: str
    outcome: str
    principal: Dict[str, Any]
    http: Dict[str, Any]
    meta: Dict[str, Any]
    resource: Optional[Dict[str, Any]] = None
    event_hash: str

    def __str__(self):
        # Canonical string representation for hashing (RFC 8785)
        import json

        clean = self.model_dump(exclude={"event_hash"})
        return json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class RootView(BaseModel):
    root: str


class ProofStep(BaseModel):
    position: str  # "left" or "right"
    hash: str


class ProofView(BaseModel):
    event_id: str
    entry_hash: str
    root: str
    height: int
    path: List[ProofStep]
    index: int
