"""Model plug-in registry.

DEC-018: models are pluggable. No model is privileged by the framework.
Register a new model by decorating its class with `@register_model`;
the class MUST inherit from `BaseModel` and set a unique `kind` string.
"""
from __future__ import annotations
from typing import Dict, Type

from learning_system.models.base import BaseModel

MODEL_REGISTRY: Dict[str, Type[BaseModel]] = {}


def register_model(cls: Type[BaseModel]) -> Type[BaseModel]:
    kind = getattr(cls, "kind", None)
    if not kind:
        raise ValueError(
            f"{cls.__name__} must define a class-level `kind` string"
        )
    if kind in MODEL_REGISTRY:
        raise ValueError(
            f"model kind {kind!r} already registered by "
            f"{MODEL_REGISTRY[kind].__name__}"
        )
    MODEL_REGISTRY[kind] = cls
    return cls


def instantiate(kind: str, hyperparams: dict, seed: int = 42) -> BaseModel:
    if kind not in MODEL_REGISTRY:
        raise ValueError(
            f"unknown model kind {kind!r}; registered: "
            f"{sorted(MODEL_REGISTRY)}"
        )
    return MODEL_REGISTRY[kind](hyperparams=hyperparams, seed=seed)


# Register concrete implementations at import time.
from learning_system.models import sklearn_models   # noqa: F401,E402
from learning_system.models import xgboost_model    # noqa: F401,E402
from learning_system.models import neural            # noqa: F401,E402
