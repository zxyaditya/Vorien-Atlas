"""Atlas Validation Framework — gates package."""
from .universal import UNIVERSAL_GATES
from .properties import PROPERTY_GATES, IDENTITY_VERIFIERS
from .registry_wide import REGISTRY_WIDE_GATES

__all__ = ["UNIVERSAL_GATES", "PROPERTY_GATES",
           "IDENTITY_VERIFIERS", "REGISTRY_WIDE_GATES"]
