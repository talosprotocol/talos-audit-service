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
        return f"{self.event_id}:{self.timestamp}:{self.event_type}:{self.details}"

class RootView(BaseModel):
    root: str

class ProofView(BaseModel):
    event_id: str
    proof: List[str]
