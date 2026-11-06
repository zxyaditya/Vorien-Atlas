from typing import Dict, Any, List
import numpy as np
from .core import _get, _make_signal, _row

def trend_momentum_signal(v: Dict[str, float]) -> dict:
    """L2 signal — TrendMomentum.
    Consumes momentum_of_trend.* features exclusively. Answers:
      'Beyond raw price motion, is the underlying trend gaining or losing
       strength, and do multiple trend representations agree?'
    See /app/docs/L2_SPECS/MOMENTUM_OF_TREND_DE_REVIEW.md for the design.
    """
    ev = []
    v_slope = _get(v, "momentum_of_trend.motion.lr_slope_20_velocity_20")
    v_adx   = _get(v, "momentum_of_trend.motion.adx_14_velocity_20")
    agree   = _get(v, "momentum_of_trend.relative.velocity_sign_agreement_20")
    persist = _get(v, "momentum_of_trend.regime.lr_slope_20_direction_persistence_20")

    # Direction from slope-velocity sign; ADX velocity reinforces it.
    if v_slope is None:
        return _make_signal("TrendMomentum", 0, 0.0, 0.3, ev)

    combined = v_slope + 0.5 * (v_adx if v_adx is not None else 0.0) * (1.0 if v_slope > 0 else -1.0 if v_slope < 0 else 0.0)
    d = +1 if combined > 1e-6 else -1 if combined < -1e-6 else 0

    # Strength: scaled |v_slope| plus persistence bonus (both bounded).
    #   |v_slope| is in units of slope/bar. Empirically on daily equities
    #   |v_slope| for lr_slope_20 sits well under 0.1 → scale by 20.
    persist_bonus = 0.0 if persist is None else min(1.0, max(0.0, persist / 20.0)) * 0.3
    strength = min(1.0, abs(v_slope) * 20.0 + persist_bonus)

    # Confidence anchored on cross-source agreement.
    conf_base = 0.4 if agree is None else min(1.0, 0.4 + 0.6 * max(0.0, min(1.0, agree)))

    ev.append(_row("momentum_of_trend.motion.lr_slope_20_velocity_20", v_slope,
                   f"Slope(20) velocity = {v_slope:+.4f} "
                   f"({'trend strengthening upward' if v_slope > 0 else 'trend strengthening downward' if v_slope < 0 else 'trend flat'})",
                   0.40))
    if v_adx is not None:
        ev.append(_row("momentum_of_trend.motion.adx_14_velocity_20", v_adx,
                       f"ADX(14) velocity = {v_adx:+.3f} "
                       f"({'directional strength rising' if v_adx > 0 else 'directional strength falling' if v_adx < 0 else 'flat'})",
                       0.20))
    if persist is not None:
        ev.append(_row("momentum_of_trend.regime.lr_slope_20_direction_persistence_20", persist,
                       f"Trend-direction persistence = {int(persist)} bars", 0.20))
    if agree is not None:
        ev.append(_row("momentum_of_trend.relative.velocity_sign_agreement_20", agree,
                       f"Cross-source agreement = {agree:.2f} "
                       f"({'all three trend proxies agree' if agree >= 0.99 else 'majority agrees' if agree >= 0.67 else 'disagreement'})",
                       0.20))

    return _make_signal("TrendMomentum", d, strength, conf_base, ev)



def trend_alignment_signal(v: Dict[str, float]) -> dict:
    """L2 signal — TrendAlignment.
    Consumes trend_relationships.* features exclusively. Answers:
      'Do multiple independent trend measurements agree on direction,
       and how cleanly does the EMA cascade reflect that direction?'
    See /app/docs/L2_SPECS/TREND_RELATIONSHIPS_DE_REVIEW.md.
    """
    ev = []
    cons_sign  = _get(v, "trend_relationships.regime.directional_consensus_sign_20")
    cons_score = _get(v, "trend_relationships.regime.directional_consensus_score_20")
    agree_flag = _get(v, "trend_relationships.regime.all_sources_agree_flag_20")
    casc_signed = _get(v, "trend_relationships.geometry.ema_cascade_signed_10_20_50_100")
    casc_score  = _get(v, "trend_relationships.geometry.ema_cascade_score_10_20_50_100")

    # Direction: consensus authoritative; fallback to cascade only when
    # cascade is unambiguous.
    if cons_sign is not None and cons_sign != 0:
        d = 1 if cons_sign > 0 else -1
    elif casc_signed is not None and abs(casc_signed) > 0.34:
        d = 1 if casc_signed > 0 else -1
    else:
        d = 0

    # Strength.
    sign_ok = 1.0
    if d != 0 and casc_signed is not None and casc_signed != 0.0:
        if (casc_signed > 0 and d < 0) or (casc_signed < 0 and d > 0):
            sign_ok = 0.5  # cascade disagrees with consensus → halved contribution
    part_cons = 0.0 if cons_score is None else max(0.0, min(1.0, 2 * cons_score - 2.0 / 3.0))
    part_casc = 0.0 if casc_signed is None else min(1.0, abs(casc_signed)) * sign_ok
    strength = min(1.0, 0.5 * part_cons + 0.5 * part_casc)

    # Confidence base from consensus score, unanimity bonus if flag set.
    if cons_score is None:
        conf = 0.30
    else:
        conf = 0.30 + 0.70 * (cons_score - 1.0 / 3.0) / (2.0 / 3.0)
        conf = max(0.0, min(1.0, conf))
    if agree_flag is not None and agree_flag >= 0.5:
        conf = min(1.0, conf + 0.20)

    if cons_sign is not None:
        ev.append(_row("trend_relationships.regime.directional_consensus_sign_20", cons_sign,
                       f"Consensus sign = {int(cons_sign):+d} "
                       f"({'up' if cons_sign > 0 else 'down' if cons_sign < 0 else 'no majority'})",
                       0.30))
    if cons_score is not None:
        ev.append(_row("trend_relationships.regime.directional_consensus_score_20", cons_score,
                       f"Consensus score = {cons_score:.2f} "
                       f"({'unanimous' if cons_score >= 0.99 else 'majority' if cons_score >= 0.66 else 'split'})",
                       0.20))
    if agree_flag is not None:
        ev.append(_row("trend_relationships.regime.all_sources_agree_flag_20", agree_flag,
                       f"All 3 methodologies agree" if agree_flag >= 0.5 else "At least one methodology disagrees",
                       0.15))
    if casc_signed is not None:
        ev.append(_row("trend_relationships.geometry.ema_cascade_signed_10_20_50_100", casc_signed,
                       f"EMA cascade (signed) = {casc_signed:+.2f} "
                       f"({'clean up' if casc_signed >= 0.66 else 'clean down' if casc_signed <= -0.66 else 'partial/broken'})",
                       0.20))
    if casc_score is not None:
        ev.append(_row("trend_relationships.geometry.ema_cascade_score_10_20_50_100", casc_score,
                       f"EMA cascade order = {casc_score:.2f} of 4 pairs correct", 0.15))

    return _make_signal("TrendAlignment", d, strength, conf, ev)





def fractal_coherence_signal(v: Dict[str, float]) -> dict:
    """L2 signal — FractalCoherence (direction-neutral).

    Consumes fractal_relationships.* features exclusively. Answers:
      'Do the market's independent scaling laws (variance-scaling,
       generalised Hurst, VR, cross-window Hurst/FD) all describe the
       same self-similar process across at least three scales, and
       how cleanly?'

    Direction is always 0 (owner directive, Session 7 P3): this is a
    direction-neutral confidence-modulator. Strength = self-similarity
    score; confidence = mapped score with unanimity bonus.

    See /app/docs/L2_SPECS/FRACTAL_RELATIONSHIPS_DE_REVIEW.md.
    """
    ev = []
    score = _get(v, "fractal_relationships.regime.self_similarity_score")
    flag  = _get(v, "fractal_relationships.regime.self_similarity_flag")
    alpha = _get(v, "fractal_relationships.geometry.variance_scaling_exponent_2_64")
    mfs   = _get(v, "fractal_relationships.statistics.multifractal_spread_h1_minus_h3_2_32")
    vrdev = _get(v, "fractal_relationships.distribution.variance_ratio_max_deviation_from_unity_2_16")

    # Direction: always 0 (owner directive).
    d = 0

    # Strength: self-similarity score (0 if unavailable).
    strength = float(score) if score is not None else 0.0

    # Confidence: score mapped [0,1] → [0.30, 1.00]; +15% if flag set.
    if score is None:
        conf = 0.30
    else:
        conf = 0.30 + 0.70 * max(0.0, min(1.0, score))
    if flag is not None and flag >= 0.5:
        conf = min(1.0, conf + 0.15)

    # Evidence rows — every argument states the value and its Brownian
    # canonical reference; interpretation stays at the L5 signal only.
    if score is not None:
        gate = "≥ 0.75 threshold — scale-invariant" if score >= 0.75 else "< 0.75 threshold — scale-heterogeneous"
        ev.append(_row("fractal_relationships.regime.self_similarity_score", score,
                       f"Self-similarity score = {score:.2f} ({gate})", 0.35))
    if flag is not None:
        ev.append(_row("fractal_relationships.regime.self_similarity_flag", flag,
                       f"All 5 scale-invariance sub-scores {'agree' if flag >= 0.5 else 'do not agree'}",
                       0.20))
    if alpha is not None:
        tag = ("Brownian" if abs(alpha - 1.0) < 0.10
               else "super-diffusive" if alpha > 1.0 else "sub-diffusive")
        ev.append(_row("fractal_relationships.geometry.variance_scaling_exponent_2_64", alpha,
                       f"Variance-scaling α = {alpha:.2f} (Brownian = 1.0; {tag})", 0.20))
    if mfs is not None:
        tag = "monofractal" if abs(mfs) < 0.05 else "multifractal"
        ev.append(_row("fractal_relationships.statistics.multifractal_spread_h1_minus_h3_2_32", mfs,
                       f"Multifractal spread H(1)−H(3) = {mfs:+.3f} (Brownian = 0; {tag})", 0.15))
    if vrdev is not None:
        tag = "random-walk consistent" if vrdev < 0.15 else "scale-dependent variance"
        ev.append(_row("fractal_relationships.distribution.variance_ratio_max_deviation_from_unity_2_16", vrdev,
                       f"VR max deviation = {vrdev:.2f} (Brownian = 0; {tag})", 0.10))

    return _make_signal("FractalCoherence", d, strength, conf, ev)





def relative_strength_signal(v: Dict[str, float]) -> dict:
    """L2 signal — RelativeStrength (direction-neutral).

    Consumes relative_strength.* features exclusively. Answers:
      'Is the target behaving strongly or weakly relative to its chosen
       benchmark, and how reliable is that comparison right now?'

    Direction is always 0 (owner directive, Session 7 P4): outperforming
    a peer does not imply LONG; both assets can fall together and the
    target can still "outperform" by falling less. This signal is a
    confidence-modulator and evidence contributor, never a directional
    vote.

    Strength: symmetric divergence from equilibrium (|rs - 1|).
    Confidence: correlation magnitude + tight-cointegration bonus.

    See /app/docs/L2_SPECS/RELATIVE_STRENGTH_DE_REVIEW.md.
    """
    ev = []
    rs20  = _get(v, "relative_strength.magnitude.rs_20")
    rs50  = _get(v, "relative_strength.magnitude.rs_50")
    corr50 = _get(v, "relative_strength.statistics.corr_50")
    relvol50 = _get(v, "relative_strength.expansion.relvol_50")
    coint = _get(v, "relative_strength.entropy.cointegration_resid_std_100")

    # Direction: always 0 (owner directive, Session 7 P4).
    d = 0

    # Strength: symmetric divergence from equilibrium (rs = 1 ⇒ same behaviour).
    parts = []
    if rs20 is not None:
        parts.append(min(1.0, abs(rs20 - 1.0)))
    if rs50 is not None:
        parts.append(min(1.0, abs(rs50 - 1.0)))
    strength = (sum(parts) / len(parts)) if parts else 0.0

    # Confidence: |corr_50| ∈ [0, 1] → [0.30, 0.90]; +10% if tight cointegration.
    if corr50 is None:
        conf = 0.30
    else:
        conf = 0.30 + 0.60 * max(0.0, min(1.0, abs(corr50)))
    if coint is not None and coint < 0.05:
        conf = min(1.0, conf + 0.10)

    # Evidence rows — descriptive only; interpretation stays at L5 signal name.
    if rs20 is not None:
        tag = ("outperforming peer" if rs20 > 1.0 else
               "underperforming peer" if rs20 < 1.0 else "aligned with peer")
        ev.append(_row("relative_strength.magnitude.rs_20", rs20,
                       f"20-bar relative return = {rs20:.3f} ({tag}; 1.0 = equal)",
                       0.30))
    if rs50 is not None:
        tag = ("outperforming peer" if rs50 > 1.0 else
               "underperforming peer" if rs50 < 1.0 else "aligned with peer")
        ev.append(_row("relative_strength.magnitude.rs_50", rs50,
                       f"50-bar relative return = {rs50:.3f} ({tag}; 1.0 = equal)",
                       0.25))
    if corr50 is not None:
        tag = ("strongly correlated pair — comparison meaningful"
               if abs(corr50) >= 0.6
               else "moderately correlated pair"
               if abs(corr50) >= 0.3
               else "weakly correlated pair — treat comparison cautiously")
        ev.append(_row("relative_strength.statistics.corr_50", corr50,
                       f"50-bar return correlation = {corr50:+.2f} ({tag})",
                       0.20))
    if relvol50 is not None:
        tag = ("target more volatile than peer" if relvol50 > 1.05
               else "peer more volatile than target" if relvol50 < 0.95
               else "similar volatility")
        ev.append(_row("relative_strength.expansion.relvol_50", relvol50,
                       f"Relative volatility (σ_a/σ_b, w=50) = {relvol50:.2f} ({tag})",
                       0.15))
    if coint is not None:
        tag = ("tight structural pair" if coint < 0.05
               else "loose structural pair" if coint > 0.15
               else "moderate structural link")
        ev.append(_row("relative_strength.entropy.cointegration_resid_std_100",
                       coint,
                       f"Cointegration residual σ (w=100) = {coint:.3f} ({tag})",
                       0.10))

    return _make_signal("RelativeStrength", d, strength, conf, ev)



def market_structure_signal(v: Dict[str, float]) -> dict:
    """Directional evidence from L2 Market Structure (BOS + regime + fractal).
    Reads only market_structure.* features. Consumes L2 via the Registry."""
    ev, votes = [], []

    bos = _get(v, "market_structure.motion.bos_k5")
    if bos is not None:
        d = +1 if bos > 0.5 else -1 if bos < -0.5 else 0
        if d != 0:
            votes.append((d, 0.45))
        ev.append(_row("market_structure.motion.bos_k5", bos,
                       f"BOS (k=5) = {bos:+.0f} "
                       f"({'break above last swing high' if bos > 0 else 'break below last swing low' if bos < 0 else 'inside range'})",
                       0.45))

    reg = _get(v, "market_structure.regime.structure_regime_k5")
    if reg is not None:
        d = +1 if reg > 0.5 else -1 if reg < -0.5 else 0
        if d != 0:
            votes.append((d, 0.30))
        ev.append(_row("market_structure.regime.structure_regime_k5", reg,
                       f"Structure regime = {reg:+.0f} "
                       f"({'bullish HH+HL' if reg > 0 else 'bearish LH+LL' if reg < 0 else 'mixed'})",
                       0.30))

    frac = _get(v, "market_structure.geometry.fractal_agreement")
    if frac is not None:
        ev.append(_row("market_structure.geometry.fractal_agreement", frac,
                       f"Fractal agreement (k=3,5,10) = {int(frac)}", 0.15))

    choch = _get(v, "market_structure.regime.choch_flag_k5")
    if choch is not None:
        ev.append(_row("market_structure.regime.choch_flag_k5", choch,
                       f"Change-of-Character flag = {int(choch)}", 0.10))

    if not votes:
        return _make_signal("MarketStructure", 0, 0.0, 0.3, ev)
    dot = sum(d * w for d, w in votes)
    total = sum(w for _, w in votes)
    dirn = 1 if dot > 0.05 else -1 if dot < -0.05 else 0
    signs = [d for d, _ in votes]
    agree = abs(sum(signs)) / len(signs) if signs else 0.0
    return _make_signal("MarketStructure", dirn, abs(dot) / total, agree, ev)



