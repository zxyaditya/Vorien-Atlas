from typing import Dict, Any, List
import numpy as np
from .core import _get, _make_signal, _row

def trend_signal(v: Dict[str, float]) -> dict:
    """Sustained directional bias. Uses regime, MA-slope, MA-cross, straightness."""
    votes = []
    ev = []

    r200 = _get(v, "price.regime.above_sma_200")
    if r200 is not None:
        d = +1 if r200 > 0 else -1
        votes.append((d, 0.30))
        ev.append(_row("price.regime.above_sma_200", r200,
                       "Price above 200-SMA" if d > 0 else "Price below 200-SMA", 0.30))

    cross = _get(v, "price.regime.ma50_above_ma200")
    if cross is not None:
        d = +1 if cross > 0.5 else -1
        votes.append((d, 0.20))
        ev.append(_row("price.regime.ma50_above_ma200", cross,
                       "SMA50 > SMA200 (golden-cross regime)" if d > 0 else
                       "SMA50 < SMA200 (death-cross regime)", 0.20))

    slope = _get(v, "price.motion.lr_slope_50")
    if slope is not None:
        d = +1 if slope > 0 else -1
        votes.append((d, 0.20))
        ev.append(_row("price.motion.lr_slope_50", slope,
                       f"OLS slope over 50 bars {'positive' if d>0 else 'negative'}", 0.20))

    r2 = _get(v, "price.geometry.lr_r2_50")
    st50 = _get(v, "price.geometry.straightness_50")
    quality = 0.0
    if r2 is not None:
        quality = max(quality, r2)
        ev.append(_row("price.geometry.lr_r2_50", r2,
                       f"Trend quality (R²) = {r2:.2f}", 0.10))
    if st50 is not None:
        quality = max(quality, st50)
        ev.append(_row("price.geometry.straightness_50", st50,
                       f"Path straightness = {st50:.2f}", 0.10))

    if not votes:
        return _make_signal("Trend", 0, 0.0, 0.0, ev)

    dot = sum(d * w for d, w in votes)
    total = sum(w for _, w in votes)
    dirn = 1 if dot > 0.05 else -1 if dot < -0.05 else 0
    strength = abs(dot) / total
    confidence = min(1.0, quality * 1.5 + 0.3 if quality > 0 else 0.4)
    return _make_signal("Trend", dirn, strength, confidence, ev)



def momentum_signal(v: Dict[str, float]) -> dict:
    """Directional acceleration and short-term push."""
    ev = []
    votes = []

    for fid, wt in [("price.motion.log_return_10", 0.25),
                    ("price.motion.log_return_20", 0.20),
                    ("price.motion.ema_diff_5_20", 0.20),
                    ("price.motion.ema_diff_20_50", 0.20)]:
        val = _get(v, fid)
        if val is not None:
            d = +1 if val > 0 else -1
            votes.append((d, wt))
            ev.append(_row(fid, val,
                           f"{fid.split('.')[-1]} = {val:.4f}", wt))

    chande = _get(v, "price.regime.chande_momentum_14")
    if chande is not None:
        d = +1 if chande > 0.1 else -1 if chande < -0.1 else 0
        if d != 0:
            votes.append((d, 0.15))
        ev.append(_row("price.regime.chande_momentum_14", chande,
                       f"Chande momentum = {chande:.2f}", 0.15))

    if not votes:
        return _make_signal("Momentum", 0, 0.0, 0.0, ev)

    dot = sum(d * w for d, w in votes)
    total = sum(w for _, w in votes)
    dirn = 1 if dot > 0.05 else -1 if dot < -0.05 else 0
    strength = abs(dot) / total
    # confidence: agreement among the votes
    if votes:
        signs = [d for d, _ in votes]
        agree = abs(sum(signs)) / len(signs)
    else:
        agree = 0.0
    return _make_signal("Momentum", dirn, strength, agree, ev)



def volatility_signal(v: Dict[str, float]) -> dict:
    """Direction-neutral state descriptor reading VOLATILITY-module features."""
    ev = []
    tercile = _get(v, "volatility.regime.tercile_200")
    sl = _get(v, "volatility.expansion.short_long_ratio", 1.0) or 1.0
    persistence = _get(v, "volatility.regime.abs_ret_persistence_60", 0.0) or 0.0
    semi_ratio = _get(v, "volatility.magnitude.semi_ratio_20", 1.0) or 1.0

    if tercile is not None:
        ev.append(_row("volatility.regime.tercile_200", tercile,
                       "High-vol regime" if tercile > 0.5 else
                       "Low-vol regime" if tercile < -0.5 else
                       "Normal-vol regime", 0.4))
    ev.append(_row("volatility.expansion.short_long_ratio", sl,
                   f"σ_10/σ_50 = {sl:.2f}", 0.3))
    ev.append(_row("volatility.regime.abs_ret_persistence_60", persistence,
                   f"|r| persistence = {persistence:.2f} — "
                   f"{'strong clustering' if persistence > 0.3 else 'weak clustering'}", 0.2))
    ev.append(_row("volatility.magnitude.semi_ratio_20", semi_ratio,
                   f"σ_up/σ_down = {semi_ratio:.2f}", 0.1))

    if tercile is not None and tercile > 0.5:
        state, strength = "elevated", min(1.0, sl / 2 + 0.5)
    elif sl < 0.75:
        state, strength = "compressed", 0.7
    else:
        state, strength = "normal", 0.3

    sig = _make_signal("Volatility", 0, strength, 0.7, ev)
    sig["state"] = state
    return sig



def volume_signal(v: Dict[str, float]) -> dict:
    """Signed participation & confirmation from the VOLUME module."""
    ev, votes = [], []

    pv = _get(v, "volume.regime.pv_confirmation_20")
    if pv is not None:
        if pv > 0.5:
            votes.append((+1, 0.35))
            ev.append(_row("volume.regime.pv_confirmation_20", pv,
                           "Price trend confirmed by volume", 0.35))
        elif pv < -0.5:
            votes.append((-1, 0.35))
            ev.append(_row("volume.regime.pv_confirmation_20", pv,
                           "Price-volume divergence (weakness)", 0.35))

    signed_ema = _get(v, "volume.regime.signed_ema_20")
    if signed_ema is not None:
        d = +1 if signed_ema > 0 else -1
        votes.append((d, 0.30))
        ev.append(_row("volume.regime.signed_ema_20", signed_ema,
                       "Net buying pressure" if d > 0 else "Net selling pressure",
                       0.30))

    pct = _get(v, "volume.position.pct_rank_100")
    if pct is not None:
        ev.append(_row("volume.position.pct_rank_100", pct,
                       f"Volume percentile = {pct:.2f} "
                       f"({'unusually high' if pct > 0.8 else 'unusually low' if pct < 0.2 else 'typical'})",
                       0.2))

    price_vs_vwap = _get(v, "volume.relative.price_vs_vwap_20")
    if price_vs_vwap is not None:
        d = +1 if price_vs_vwap > 0 else -1
        votes.append((d, 0.15))
        ev.append(_row("volume.relative.price_vs_vwap_20", price_vs_vwap,
                       f"Price {'above' if d>0 else 'below'} VWAP_20", 0.15))

    if not votes:
        return _make_signal("Volume", 0, 0.0, 0.3, ev)

    dot = sum(d * w for d, w in votes)
    total = sum(w for _, w in votes)
    dirn = 1 if dot > 0.05 else -1 if dot < -0.05 else 0
    signs = [d for d, _ in votes]
    agree = abs(sum(signs)) / len(signs) if signs else 0.0
    return _make_signal("Volume", dirn, abs(dot) / total, agree, ev)



def liquidity_signal(v: Dict[str, float]) -> dict:
    """Direction-neutral state descriptor reading LIQUIDITY-module features."""
    ev = []
    tercile = _get(v, "liquidity.regime.tercile_200")
    sl = _get(v, "liquidity.expansion.short_long_ratio", 1.0) or 1.0
    kyle = _get(v, "liquidity.regime.kyle_above_ma_50")
    turnover = _get(v, "liquidity.magnitude.turnover_20", 1.0) or 1.0

    if tercile is not None:
        ev.append(_row("liquidity.regime.tercile_200", tercile,
                       "Illiquid regime" if tercile > 0.5 else
                       "Liquid regime" if tercile < -0.5 else
                       "Normal-liquidity regime", 0.4))
    ev.append(_row("liquidity.expansion.short_long_ratio", sl,
                   f"Amihud_10/Amihud_50 = {sl:.2f}", 0.3))
    if kyle is not None:
        ev.append(_row("liquidity.regime.kyle_above_ma_50", kyle,
                       "Elevated price impact" if kyle > 0 else "Normal price impact", 0.2))
    ev.append(_row("liquidity.magnitude.turnover_20", turnover,
                   f"Turnover = {turnover:.2f}", 0.1))

    # State labeling (direction-neutral)
    if tercile is not None and tercile > 0.5:
        state, strength = "illiquid", 0.8
    elif tercile is not None and tercile < -0.5:
        state, strength = "liquid", 0.4
    else:
        state, strength = "normal", 0.3

    sig = _make_signal("Liquidity", 0, strength, 0.65, ev)
    sig["state"] = state
    return sig



def structure_signal(v: Dict[str, float]) -> dict:
    """Path structure — trending vs mean-reverting via Hurst + straightness."""
    ev, votes = [], []

    hurst = _get(v, "price.geometry.hurst_64")
    if hurst is not None:
        # >0.5 persistent, <0.5 mean-reverting
        if hurst > 0.55:
            ev.append(_row("price.geometry.hurst_64", hurst,
                           f"Persistent (H={hurst:.2f}) — trend continuation favored", 0.4))
        elif hurst < 0.45:
            ev.append(_row("price.geometry.hurst_64", hurst,
                           f"Mean-reverting (H={hurst:.2f}) — reversal risk", 0.4))
        else:
            ev.append(_row("price.geometry.hurst_64", hurst,
                           f"Random-walk-like (H={hurst:.2f})", 0.4))

    chop = _get(v, "price.regime.choppiness_14")
    if chop is not None:
        ev.append(_row("price.regime.choppiness_14", chop,
                       f"Choppiness = {chop:.2f} " +
                       ("(range-bound)" if chop > 0.6 else "(trending)" if chop < 0.4 else "(mixed)"),
                       0.3))

    fd = _get(v, "price.geometry.higuchi_fd_50")
    if fd is not None:
        ev.append(_row("price.geometry.higuchi_fd_50", fd,
                       f"Fractal dimension = {fd:.2f} " +
                       ("(rough)" if fd > 1.5 else "(smooth)"), 0.3))

    # Structure gives a signed vote when Hurst supports the current trend
    if hurst is not None:
        # We rely on trend_signal for direction; structure just confirms/denies
        return _make_signal("Structure", 0,
                            abs((hurst or 0.5) - 0.5) * 2,
                            0.7 if hurst is not None else 0.3, ev)
    return _make_signal("Structure", 0, 0.0, 0.0, ev)



def entropy_signal(v: Dict[str, float]) -> dict:
    """Predictability — low entropy → predictable regime → higher confidence."""
    ev = []
    strengths = []
    for fid in ["price.entropy.perm_o3_w30", "price.entropy.spectral_60",
                "price.entropy.sample_60"]:
        val = _get(v, fid)
        if val is not None:
            ev.append(_row(fid, val,
                           f"{fid.split('.')[-1]} = {val:.2f}", 0.3))
            strengths.append(val)
    if not strengths:
        return _make_signal("Entropy", 0, 0.0, 0.0, ev)
    mean_ent = np.mean(strengths)
    predictability = 1.0 - min(mean_ent, 1.0)
    sig = _make_signal("Entropy", 0, predictability, 0.6, ev)
    sig["state"] = ("predictable" if predictability > 0.6 else
                    "chaotic" if predictability < 0.3 else "mixed")
    return sig



def meanrev_signal(v: Dict[str, float]) -> dict:
    """Overbought/oversold via Bollinger %B, Fisher, distance-from-MA."""
    ev, votes = [], []
    bb = _get(v, "price.position.bb_percent_b_20_k2")
    if bb is not None:
        if bb > 1.0:
            votes.append((-1, 0.4))
            ev.append(_row("price.position.bb_percent_b_20_k2", bb,
                           f"Above upper Bollinger band (%B={bb:.2f})", 0.4))
        elif bb < 0.0:
            votes.append((+1, 0.4))
            ev.append(_row("price.position.bb_percent_b_20_k2", bb,
                           f"Below lower Bollinger band (%B={bb:.2f})", 0.4))

    fisher = _get(v, "price.position.fisher_20")
    if fisher is not None:
        if fisher > 1.5:
            votes.append((-1, 0.3))
            ev.append(_row("price.position.fisher_20", fisher,
                           f"Fisher stretched high ({fisher:.2f})", 0.3))
        elif fisher < -1.5:
            votes.append((+1, 0.3))
            ev.append(_row("price.position.fisher_20", fisher,
                           f"Fisher stretched low ({fisher:.2f})", 0.3))

    z = _get(v, "price.statistics.zscore_20")
    if z is not None:
        if z > 2.0:
            votes.append((-1, 0.3))
            ev.append(_row("price.statistics.zscore_20", z,
                           f"Extended (Z={z:.2f})", 0.3))
        elif z < -2.0:
            votes.append((+1, 0.3))
            ev.append(_row("price.statistics.zscore_20", z,
                           f"Oversold (Z={z:.2f})", 0.3))

    if not votes:
        return _make_signal("MeanReversion", 0, 0.0, 0.3, ev)

    dot = sum(d * w for d, w in votes)
    total = sum(w for _, w in votes)
    dirn = 1 if dot > 0.05 else -1 if dot < -0.05 else 0
    return _make_signal("MeanReversion", dirn, abs(dot) / total, 0.6, ev)



def regime_signal(v: Dict[str, float]) -> dict:
    """Aroon + Vortex + ADX-like directional agreement."""
    ev, votes = [], []

    au = _get(v, "price.regime.aroon_up_14")
    ad = _get(v, "price.regime.aroon_dn_14")
    if au is not None and ad is not None:
        if au > 70 and ad < 30:
            votes.append((+1, 0.4))
            ev.append(_row("price.regime.aroon_up_14", au,
                           f"Aroon Up dominates ({au:.0f} vs {ad:.0f})", 0.4))
        elif ad > 70 and au < 30:
            votes.append((-1, 0.4))
            ev.append(_row("price.regime.aroon_dn_14", ad,
                           f"Aroon Down dominates ({ad:.0f} vs {au:.0f})", 0.4))

    vp = _get(v, "price.regime.vortex_up_14")
    vn = _get(v, "price.regime.vortex_dn_14")
    if vp is not None and vn is not None:
        if vp - vn > 0.1:
            votes.append((+1, 0.3))
            ev.append(_row("price.regime.vortex_up_14", vp,
                           f"Vortex Up > Down ({vp:.2f} vs {vn:.2f})", 0.3))
        elif vn - vp > 0.1:
            votes.append((-1, 0.3))
            ev.append(_row("price.regime.vortex_dn_14", vn,
                           f"Vortex Down > Up ({vn:.2f} vs {vp:.2f})", 0.3))

    adx = _get(v, "price.regime.adx_14")
    if adx is not None:
        ev.append(_row("price.regime.adx_14", adx,
                       f"Directional strength (ADX-like) = {adx:.0f}", 0.3))

    if not votes:
        return _make_signal("Regime", 0, 0.0, 0.3, ev)
    dot = sum(d * w for d, w in votes)
    total = sum(w for _, w in votes)
    dirn = 1 if dot > 0.05 else -1 if dot < -0.05 else 0
    return _make_signal("Regime", dirn, abs(dot) / total,
                        min(1.0, (adx or 0) / 40 + 0.4), ev)



def microstructure_signal(v: Dict[str, float]) -> dict:
    """Directional evidence from L1 Microstructure (candle anatomy + participation).
    Book 1 L1 primitive consumer — reads only microstructure.* features.
    """
    ev, votes = [], []

    exec_imb = _get(v, "microstructure.expansion.execution_imbalance_20")
    if exec_imb is not None:
        d = +1 if exec_imb > 0.1 else -1 if exec_imb < -0.1 else 0
        if d != 0:
            votes.append((d, 0.35))
        ev.append(_row("microstructure.expansion.execution_imbalance_20", exec_imb,
                       f"Execution imbalance {exec_imb:+.2f} "
                       f"({'up-body dominates' if exec_imb > 0 else 'down-body dominates' if exec_imb < 0 else 'balanced'})",
                       0.35))

    rc = _get(v, "microstructure.expansion.range_covered_20")
    if rc is not None:
        ev.append(_row("microstructure.expansion.range_covered_20", rc,
                       f"Range-covered ratio = {rc:.2f} "
                       f"({'directional auction' if rc > 0.4 else 'rotational' if rc < 0.2 else 'mixed'})",
                       0.20))

    wd = _get(v, "microstructure.geometry.wick_difference_ratio")
    if wd is not None:
        d = -1 if wd > 0.4 else +1 if wd < -0.4 else 0
        if d != 0:
            votes.append((d, 0.25))
        ev.append(_row("microstructure.geometry.wick_difference_ratio", wd,
                       f"Wick diff = {wd:+.2f} "
                       f"({'upper-side rejection' if wd > 0 else 'lower-side rejection' if wd < 0 else 'balanced wicks'})",
                       0.25))

    hp = _get(v, "microstructure.regime.high_participation_flag_20")
    if hp is not None:
        ev.append(_row("microstructure.regime.high_participation_flag_20", hp,
                       f"High-participation flag = {int(hp)}", 0.20))

    if not votes:
        return _make_signal("Microstructure", 0, 0.0, 0.3, ev)
    dot = sum(d * w for d, w in votes)
    total = sum(w for _, w in votes)
    dirn = 1 if dot > 0.05 else -1 if dot < -0.05 else 0
    signs = [d for d, _ in votes]
    agree = abs(sum(signs)) / len(signs) if signs else 0.0
    return _make_signal("Microstructure", dirn, abs(dot) / total, agree, ev)



