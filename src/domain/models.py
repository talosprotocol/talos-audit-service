from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, Any, List


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    timestamp: float
    event_type: str
    details: Dict[str, Any] = Field(default_factory=dict)

    def __str__(self):
        # Canonical string representation for hashing
        # In production, use JSON with sorted keys or Protobuf
        import json
        details_json = json.dumps(self.details, sort_keys=True)
        return f"{self.event_id}:{self.timestamp}:{self.event_type}:{details_json}"


class RootView(BaseModel):
    root: str


class ProofStep(BaseModel):
    position: str # "left" or "right"
    hash: str

class ProofView(BaseModel):
    event_id: str
    entry_hash: str
    root: str
    height: int
    path: List[ProofStep]
    index: int
