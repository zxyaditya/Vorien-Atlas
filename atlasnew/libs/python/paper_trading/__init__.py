"""Paper Trading — Layer 5 sibling of Decision Engine and Learning System.

Atlas recommendation → open paper position → tracking → automatic TP/SL /
manual close → trade history → performance analytics.

Every trade permanently snapshots the full Atlas recommendation (22 signals,
confidence, ML advisor, analogues, L3 regime, L4 embedding IDs) so the user
can later audit exactly why Atlas entered the position.

Book 1 stance: Paper Trading is a *consumer* of Atlas Core (Invariant 5.5 —
sibling to DE and LS at Layer 5). It never touches feature computation and
never imports from `learning_system` or `decision_engine`; the FastAPI
composition layer passes recommendation payloads in as plain dicts (mirror
of DEC-017 / DEC-019).
"""

__version__ = "1.0.0"
