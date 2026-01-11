from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, Any, List


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    timestamp: float
    event_type: str
    schema_id: str = "talos.audit.v1"
    schema_version: int = 1
    details: Dict[str, Any] = Field(default_factory=dict)

    def __str__(self):
        # Canonical string representation for hashing
        from talos_sdk.canonical import canonical_json

        core = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "details": self.details,
        }
        return canonical_json(core)


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
