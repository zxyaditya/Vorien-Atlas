"""Engines — domain-neutral mathematical machinery.

Engines never know about markets. They compute pure mathematics.
Modules consume engines; engines never consume modules.
Book 1: "Abstractions are discovered, not assumed."
"""
from atlas_core.engines import rolling, statistics, motion, geometry
from atlas_core.engines import distribution, normalization, distance

__all__ = ["rolling", "statistics", "motion", "geometry",
           "distribution", "normalization", "distance"]
