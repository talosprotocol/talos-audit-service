import os
import sys
from talos_config import ConfigurationLoader

class AuditConfig:
    def __init__(self):
        loader = ConfigurationLoader("audit")
        
        # Legacy Shim
        legacy_defaults = {}
        if os.getenv("TALOS_STORAGE_TYPE"):
            legacy_defaults["storage_type"] = os.getenv("TALOS_STORAGE_TYPE")
            print("WARNING: Using legacy env var TALOS_STORAGE_TYPE. Please update to config.yaml or TALOS__STORAGE_TYPE.", file=sys.stderr)

        # Load Configuration
        self._data = loader.load(defaults=legacy_defaults)
        
        self.contracts_version = "1.2.0"
        self.config_version = self._data.get("config_version", "1.0")
        self.config_digest = loader.validate()

    @property
    def storage_type(self) -> str:
        return self._data.get("storage_type", "memory")

settings = AuditConfig()
