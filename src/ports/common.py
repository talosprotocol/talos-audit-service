from abc import ABC, abstractmethod
import time
import uuid
from typing import Optional

class IClockPort(ABC):
    @abstractmethod
    def now(self) -> float:
        pass

class IIdPort(ABC):
    @abstractmethod
    def generate_id(self) -> str:
        pass

class SystemClockAdapter(IClockPort):
    def now(self) -> float:
        return time.time()

class UuidIdAdapter(IIdPort):
    def generate_id(self) -> str:
        return str(uuid.uuid4())
