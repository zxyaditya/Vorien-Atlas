"""Time Module — Layer 1.

Time itself is a market property. Calendar effects, session structure,
and cyclical patterns are objectively measurable properties that ML models
find valuable when properly encoded.

All features are derived from the DataFrame's DatetimeIndex.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from atlas_core.registry.registry import registry, FeatureDefinition

MODULE = "time"


def _reg(id_, name, perspective, family, definition, formula, interp, fn,
         params=None, complexity="O(n)"):
    registry.register(FeatureDefinition(
        id=id_, name=name, layer=1, module=MODULE,
        perspective=perspective, family=family,
        definition=definition, formula=formula, interpretation=interp,
        inputs=["_index"], params=params or {},
        complexity=complexity, fn=fn,
    ))


def _idx(df) -> pd.DatetimeIndex:
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index
    return pd.to_datetime(df.index)


def _cyc(values: np.ndarray, period: float, kind: str) -> np.ndarray:
    theta = 2 * np.pi * (values / period)
    return np.sin(theta) if kind == "sin" else np.cos(theta)


# ═══════════════════════════════════════════════════════════════════════
# MAGNITUDE — raw calendar quantities
# ═══════════════════════════════════════════════════════════════════════
_reg("time.magnitude.day_of_week", "Day of Week", "Magnitude", "calendar",
     "Weekday index (Monday=0 … Sunday=6).",
     "idx.dayofweek",
     "Which weekday the bar belongs to.",
     lambda df: pd.Series(_idx(df).dayofweek.values, index=df.index, dtype=float))

_reg("time.magnitude.hour_of_day", "Hour of Day", "Magnitude", "calendar",
     "Hour of day (0..23).", "idx.hour",
     "Session position by clock hour.",
     lambda df: pd.Series(_idx(df).hour.values, index=df.index, dtype=float))

_reg("time.magnitude.day_of_month", "Day of Month", "Magnitude", "calendar",
     "Day-of-month (1..31).", "idx.day",
     "Where in the calendar month.",
     lambda df: pd.Series(_idx(df).day.values, index=df.index, dtype=float))

_reg("time.magnitude.month_of_year", "Month of Year", "Magnitude", "calendar",
     "Month index (1..12).", "idx.month",
     "Calendar month — captures seasonality.",
     lambda df: pd.Series(_idx(df).month.values, index=df.index, dtype=float))

_reg("time.magnitude.quarter", "Quarter", "Magnitude", "calendar",
     "Quarter of the year (1..4).", "idx.quarter",
     "Which quarter — earnings-cycle proxy.",
     lambda df: pd.Series(_idx(df).quarter.values, index=df.index, dtype=float))

_reg("time.magnitude.week_of_year", "Week of Year", "Magnitude", "calendar",
     "ISO week number (1..53).", "idx.isocalendar().week",
     "Week of the calendar year.",
     lambda df: pd.Series(_idx(df).isocalendar().week.values, index=df.index, dtype=float))


# ═══════════════════════════════════════════════════════════════════════
# GEOMETRY — cyclic encodings (sin/cos on unit circle)
# ═══════════════════════════════════════════════════════════════════════
_CYCLIC = [
    ("dow", 7, lambda i: i.dayofweek.values,   "day-of-week"),
    ("hod", 24, lambda i: i.hour.values,        "hour-of-day"),
    ("dom", 31, lambda i: i.day.values,         "day-of-month"),
    ("moy", 12, lambda i: (i.month.values - 1), "month-of-year"),
]
for key, period, extractor, human in _CYCLIC:
    for kind in ("sin", "cos"):
        _reg(f"time.geometry.{key}_{kind}",
             f"{human} {kind}", "Geometry", "cyclic_encoding",
             f"{kind}(2π·{human}/{period}).",
             f"{kind}(2π·{human}/{period})",
             "Continuous cyclic encoding of calendar time.",
             (lambda ex_, p_, k_: (lambda df: pd.Series(
                 _cyc(ex_(_idx(df)).astype(float), p_, k_),
                 index=df.index)))(extractor, period, kind),
             params={"period": period, "kind": kind})


# ═══════════════════════════════════════════════════════════════════════
# REGIME — boolean session/calendar flags
# ═══════════════════════════════════════════════════════════════════════
def _flag(fn):
    return lambda df: pd.Series(fn(_idx(df)).astype(float), index=df.index)


_reg("time.regime.is_month_start", "Is Month Start", "Regime", "calendar_flag",
     "1 if the bar is on the first day of a month.",
     "1[idx.day == 1]", "Month-turn effect flag.",
     _flag(lambda i: i.day == 1))

_reg("time.regime.is_month_end", "Is Month End", "Regime", "calendar_flag",
     "1 if bar is on the last day of its month.",
     "1[idx.is_month_end]", "Month-end rebalancing effect flag.",
     _flag(lambda i: i.is_month_end))

_reg("time.regime.is_quarter_start", "Is Quarter Start",
     "Regime", "calendar_flag",
     "1 if the bar is on the first day of a quarter.",
     "1[idx.is_quarter_start]", "Quarter-start flag.",
     _flag(lambda i: i.is_quarter_start))

_reg("time.regime.is_quarter_end", "Is Quarter End",
     "Regime", "calendar_flag",
     "1 if the bar is on the last day of a quarter.",
     "1[idx.is_quarter_end]", "Quarter-end flag — rebalancing pressure.",
     _flag(lambda i: i.is_quarter_end))

_reg("time.regime.is_year_start", "Is Year Start",
     "Regime", "calendar_flag",
     "1 if the bar is on the first day of a year.",
     "1[idx.is_year_start]", "Year-turn flag.",
     _flag(lambda i: i.is_year_start))

_reg("time.regime.is_year_end", "Is Year End",
     "Regime", "calendar_flag",
     "1 if the bar is on the last day of a year.",
     "1[idx.is_year_end]", "Year-end flag — tax-loss / rebalancing.",
     _flag(lambda i: i.is_year_end))

_reg("time.regime.is_weekday", "Is Weekday", "Regime", "calendar_flag",
     "1 if Mon-Fri, 0 if Sat-Sun.",
     "1[dayofweek < 5]",
     "Excludes weekends (matters for 24/7 crypto).",
     _flag(lambda i: i.dayofweek < 5))

_reg("time.regime.is_monday", "Is Monday", "Regime", "calendar_flag",
     "1 if the bar is a Monday.",
     "1[dayofweek == 0]", "Monday effect flag.",
     _flag(lambda i: i.dayofweek == 0))

_reg("time.regime.is_friday", "Is Friday", "Regime", "calendar_flag",
     "1 if the bar is a Friday.",
     "1[dayofweek == 4]", "Friday effect flag.",
     _flag(lambda i: i.dayofweek == 4))


# ═══════════════════════════════════════════════════════════════════════
# MOTION — elapsed time between bars (in seconds), useful for irregular data
# ═══════════════════════════════════════════════════════════════════════
def _elapsed(df):
    idx = _idx(df)
    dt = pd.Series(idx, index=df.index).diff().dt.total_seconds().fillna(0)
    return dt

_reg("time.motion.elapsed_seconds", "Elapsed Seconds", "Motion", "gap",
     "Seconds since the previous bar's timestamp.",
     "t_i - t_{i-1}",
     "Irregular sampling detector; sharp jumps = weekend/holiday gap.",
     _elapsed)


# ═══════════════════════════════════════════════════════════════════════
# POSITION — fractional position within calendar periods
# ═══════════════════════════════════════════════════════════════════════
_reg("time.position.month_progress", "Fraction of Month Elapsed",
     "Position", "calendar_fraction",
     "Day-of-month / days-in-month ∈ [0,1].",
     "day / days_in_month",
     "How far through the current month.",
     lambda df: pd.Series(_idx(df).day / _idx(df).days_in_month,
                          index=df.index, dtype=float))

_reg("time.position.year_progress", "Fraction of Year Elapsed",
     "Position", "calendar_fraction",
     "Day-of-year / 365(6) ∈ [0,1].",
     "dayofyear / days_in_year",
     "How far through the current year.",
     lambda df: pd.Series(
         _idx(df).dayofyear /
         np.where(_idx(df).is_leap_year, 366, 365),
         index=df.index, dtype=float))

_reg("time.position.week_progress", "Fraction of Week Elapsed",
     "Position", "calendar_fraction",
     "(dayofweek + hour/24) / 7 ∈ [0,1].",
     "(dow + hour/24)/7",
     "Continuous week position, sub-daily aware.",
     lambda df: pd.Series(
         (_idx(df).dayofweek + _idx(df).hour / 24.0) / 7.0,
         index=df.index, dtype=float))
