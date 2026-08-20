from __future__ import annotations

from typing import Any, Dict, Optional

from core.settings import (
    MIN_SL_DISTANCE,
    MULTI_TP_ENABLED,
    MULTI_TP_PROFILE,
    MULTI_TP_STRATEGY_ENABLED,
)


def _to_ratio(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        value = float(value)
    except (TypeError, ValueError):
        return default
    if value > 1.0:
        return value / 100.0
    return max(0.0, min(1.0, value))


def _normalize(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _strategy_factor(strategy: Optional[str]) -> float:
    key = str(strategy or "").upper()
    if key in {"SMC"}:
        return 1.05
    if key in {"SCALP"}:
        return 0.95
    if key in {"MICRO"}:
        return 0.90
    if key in {"SWING", "DAILY"}:
        return 1.15
    return 1.0


def _regime_factor(market_regime: Optional[str]) -> float:
    key = str(market_regime or "").upper()
    mapping = {
        "TRENDING": 0.95,
        "RANGING": 1.00,
        "VOLATILE": 1.18,
        "CRISIS": 1.28,
        "UNKNOWN": 1.05,
    }
    return mapping.get(key, 1.00)


def _session_factor(session: Optional[str]) -> float:
    key = str(session or "").upper()
    mapping = {
        "LONDON": 1.00,
        "NEWYORK": 0.98,
        "OVERLAP": 0.94,
        "ASIA": 1.06,
        "OFF_HOURS": 1.08,
    }
    return mapping.get(key, 1.00)


def _execution_factor(execution_grade: Optional[str]) -> float:
    key = str(execution_grade or "").upper()
    mapping = {
        "ELITE": 0.92,
        "A+": 0.94,
        "A": 0.96,
        "B": 1.00,
        "C": 1.08,
        "REJECT": 1.14,
    }
    return mapping.get(key, 1.00)


def _lot_factor(lot: float) -> float:
    lot_value = max(0.0, float(lot or 0.0))
    if lot_value <= 0:
        return 1.0
    normalized = lot_value / 0.20
    return 1.0 + (0.35 * (normalized ** 0.85))


def _structure_atr_buffer(
    atr_value: float,
    volatility_ratio: float,
    spread_pct: float,
    session_scale: float,
    execution_scale: float,
    regime_scale: float,
    structure_ratio: float,
) -> float:
    base = atr_value * (0.35 + (volatility_ratio * 0.45) + min(spread_pct / 100.0, 0.4))
    base *= 1.0 + ((session_scale - 1.0) * 0.08)
    base *= 1.0 + ((execution_scale - 1.0) * 0.10)
    base *= 1.0 + ((regime_scale - 1.0) * 0.06)
    base *= 1.0 + max(-0.10, min(0.20, (0.40 - structure_ratio * 0.30)))
    return max(atr_value * 0.10, min(base, atr_value * 1.75))


def calculate_adaptive_sl_tp(
    *,
    atr: float,
    strategy: Optional[str] = None,
    lot: float = 0.01,
    confidence: float = 0.5,
    quality_score: float = 50.0,
    market_regime: Optional[str] = None,
    session: Optional[str] = None,
    structure_strength: float = 0.5,
    liquidity: float = 0.5,
    volatility: float = 0.5,
    spread: float = 0.0,
    execution_grade: Optional[str] = None,
    broker_stop_level: float = 0.0,
    broker_stop_fallback: float = 0.0,
    min_sl: float = 0.0,
    max_sl: float = 1500.0,
    entry_price: Optional[float] = None,
    signal: Optional[str] = None,
    structure_context: Optional[Dict[str, Any]] = None,
    structure_analysis: Optional[Dict[str, Any]] = None,
    final_brain: Optional[Any] = None,
    strategy_dna: Optional[Any] = None,
) -> Dict[str, Any]:
    """Return adaptive SL/TP values using ATR as the primary driver.

    The engine is intentionally driven by live market context instead of fixed
    hardcoded values. Safety bounds are only applied at the very end.
    """

    atr_value = max(0.0, float(atr or 0.0))
    if atr_value <= 0:
        return {
            "sl_distance": 0.0,
            "tp_distance": 0.0,
            "risk_reward": 0.0,
            "stop_distance": 0.0,
            "dynamic_rr": 0.0,
            "reason": "ATR_INVALID",
        }

    confidence_ratio = _to_ratio(confidence, 0.5)
    quality_ratio = _to_ratio(quality_score, 0.5)
    structure_ratio = _to_ratio(structure_strength, 0.5)
    liquidity_ratio = _to_ratio(liquidity, 0.5)
    volatility_ratio = _to_ratio(volatility, 0.5)
    spread_ratio = max(0.0, float(spread or 0.0))

    brain_value = 0.0
    if isinstance(final_brain, (int, float)):
        brain_value = float(final_brain)
    elif isinstance(final_brain, dict):
        brain_value = float(final_brain.get("final_score", final_brain.get("score", 0)) or 0)
    brain_ratio = _to_ratio(brain_value, 0.5)

    dna_value = 0.0
    if isinstance(strategy_dna, (int, float)):
        dna_value = float(strategy_dna)
    elif isinstance(strategy_dna, dict):
        dna_value = float(strategy_dna.get("score", strategy_dna.get("dna_score", 0)) or 0)
    dna_ratio = _to_ratio(dna_value, 0.5)

    strategy_scale = _strategy_factor(strategy)
    regime_scale = _regime_factor(market_regime)
    session_scale = _session_factor(session)
    execution_scale = _execution_factor(execution_grade)
    lot_scale = _lot_factor(lot)

    quality_bias = 0.96 + (quality_ratio * 0.12)
    confidence_bias = 0.96 + (confidence_ratio * 0.12)
    structure_bias = 0.95 + (structure_ratio * 0.14)
    liquidity_bias = 0.92 + (liquidity_ratio * 0.16)
    volatility_bias = 1.00 + (volatility_ratio * 0.70)
    spread_bias = 1.00 + (spread_ratio / 100.0) * 0.45

    # [FER3ON-FIX-2026-08-19] TIGHTER SL - real data proved avg_loss > avg_win.
    # Base 6.0 -> 4.5, secondary coefficients reduced. Range 6.0-11.3 -> 4.5-8.5 (~25% tighter).
    sl_multiplier = (
        4.5
        + (quality_ratio * 1.2)
        + (confidence_ratio * 0.8)
        + (structure_ratio * 0.6)
        + (liquidity_ratio * 0.5)
        + (volatility_ratio * 0.6)
        + (0.25 if str(market_regime or "").upper() in {"VOLATILE", "CRISIS"} else 0.0)
        + (0.15 if str(market_regime or "").upper() == "TRENDING" else 0.0)
        + (0.20 if str(strategy or "").upper() in {"SWING", "DAILY"} else 0.0)
        + (0.15 if str(execution_grade or "").upper() in {"A", "A+", "ELITE"} else 0.0)
        + (lot_scale * 0.30)
        + (brain_ratio * 0.25)
        + (dna_ratio * 0.20)
    )

    sl_distance = atr_value * sl_multiplier

    safety_floor = float(min_sl or 0.0)
    if safety_floor <= 0:
        safety_floor = 100.0

    if max_sl is None:
        max_sl = 1500.0
    max_sl_value = max(float(max_sl), safety_floor)

    structure_candidates: Dict[str, float] = {}
    base_context = structure_context or {}
    if structure_analysis:
        base_context = {**base_context, **structure_analysis}
    if base_context:
        entry = float(entry_price or 0.0)
        signal_dir = str(signal or "").upper()
        if entry > 0:
            if "swing_high" in base_context and signal_dir == "SELL":
                swing_distance = abs(entry - float(base_context.get("swing_high", 0) or 0))
                structure_candidates["swing"] = swing_distance
            if "swing_low" in base_context and signal_dir == "BUY":
                swing_distance = abs(entry - float(base_context.get("swing_low", 0) or 0))
                structure_candidates["swing"] = swing_distance
            if "order_block" in base_context:
                structure_candidates["order_block"] = abs(entry - float(base_context.get("order_block", 0) or 0))
            if "fair_value_gap" in base_context:
                structure_candidates["fair_value_gap"] = abs(entry - float(base_context.get("fair_value_gap", 0) or 0))
            if "liquidity_zone" in base_context:
                structure_candidates["liquidity"] = abs(entry - float(base_context.get("liquidity_zone", 0) or 0))
            broker_minimum = float(base_context.get("broker_minimum", broker_stop_level or 0) or 0)
            if broker_minimum > 0:
                structure_candidates["broker_min"] = broker_minimum

    structure_base_distance = max([sl_distance, *[value for value in structure_candidates.values() if value > 0]], default=sl_distance)
    selected_source = "atr"
    selected_distance = sl_distance
    buffer_distance = _structure_atr_buffer(
        atr_value=atr_value,
        volatility_ratio=volatility_ratio,
        spread_pct=spread_ratio,
        session_scale=session_scale,
        execution_scale=execution_scale,
        regime_scale=regime_scale,
        structure_ratio=structure_ratio,
    )

    if structure_candidates:
        best_candidate = max(structure_candidates.items(), key=lambda item: item[1])
        structure_strength_ratio = _to_ratio(structure_strength, 0.5)
        if best_candidate[1] > 0:
            if str(strategy or "").upper() in {"SWING", "DAILY"} and structure_strength_ratio >= 0.50:
                selected_source = "structure"
                selected_distance = best_candidate[1] + buffer_distance
            elif best_candidate[1] > sl_distance:
                selected_source = "structure"
                selected_distance = best_candidate[1] + buffer_distance
            else:
                selected_distance = max(sl_distance, best_candidate[1] + buffer_distance)

    if broker_stop_level and float(broker_stop_level) > 0:
        selected_distance = max(selected_distance, float(broker_stop_level))
        if selected_distance == float(broker_stop_level) and selected_source != "structure":
            selected_source = "broker"

    # [FER3ON-FIX-2026-08-19] CORE FIX: actual R:R 0.67-0.93 -> forced 1.5-3.2
    # Base 1.20 -> 1.60, positive coeffs increased, negatives reduced.
    # Range floor 1.15 -> 1.5 (matches new tp1_rr); ceiling 2.2 -> 3.2.
    rr_base = 1.60
    rr_base += confidence_ratio * 0.85
    rr_base += quality_ratio * 0.75
    rr_base += liquidity_ratio * 0.30
    rr_base += structure_ratio * 0.30
    rr_base += (0.20 if str(execution_grade or "").upper() in {"A", "A+", "ELITE"} else 0.0)
    rr_base -= volatility_ratio * 0.12
    rr_base -= (0.15 if str(market_regime or "").upper() == "CRISIS" else 0.0)
    rr_base += (0.10 if str(strategy or "").upper() in {"SWING", "DAILY"} else 0.0)
    rr_base += (lot_scale - 1.0) * 0.30
    rr_base += brain_ratio * 0.25
    rr_base += dna_ratio * 0.15

    # HARD FLOOR at 1.5 to prevent avg_win < avg_loss inversion; ceiling raised to 3.2
    risk_reward = _normalize(rr_base, 1.5, 3.2)

    if broker_stop_level and float(broker_stop_level) > 0:
        safety_floor = max(safety_floor, float(broker_stop_level))
    elif safety_floor <= 0 and broker_stop_fallback and float(broker_stop_fallback) > 0:
        safety_floor = float(broker_stop_fallback)

    selected_distance = _normalize(selected_distance, safety_floor, max_sl_value)
    sl_distance = _normalize(selected_distance, safety_floor, max_sl_value)
    tp_distance = sl_distance * risk_reward

    def _build_tp_tiers(
        strategy: Optional[str],
        sl_distance_value: float,
        tp_distance_value: float,
        risk_reward_value: float,
        entry_price_value: Optional[float],
        signal_value: Optional[str],
    ) -> list[Dict[str, Any]]:
        strat_key = str(strategy or "").upper()
        tiers: list[Dict[str, Any]] = []
        if (
            MULTI_TP_ENABLED
            and MULTI_TP_STRATEGY_ENABLED.get(strat_key, True)
            and strat_key in MULTI_TP_PROFILE
        ):
            profile = MULTI_TP_PROFILE[strat_key]
            for i in range(1, 4):
                pct = float(profile.get(f"tp{i}_pct", 0) or 0)
                rr = float(profile.get(f"tp{i}_rr", 0) or 0)
                if pct <= 0 or rr <= 0:
                    continue
                distance = round(sl_distance_value * rr, 2)
                price = None
                if entry_price_value is not None:
                    direction = str(signal_value or "").upper()
                    if direction in {"BUY", "0"}:
                        price = round(float(entry_price_value) + distance, 5)
                    elif direction in {"SELL", "1"}:
                        price = round(float(entry_price_value) - distance, 5)
                tiers.append({
                    "label": f"TP{i}",
                    "close_pct": pct,
                    "rr": rr,
                    "price_distance": distance,
                    "price": price,
                })
        if not tiers:
            price = None
            if entry_price_value is not None:
                direction = str(signal_value or "").upper()
                if direction in {"BUY", "0"}:
                    price = round(float(entry_price_value) + tp_distance_value, 5)
                elif direction in {"SELL", "1"}:
                    price = round(float(entry_price_value) - tp_distance_value, 5)
            tiers = [
                {
                    "label": "TP1",
                    "close_pct": 1.0,
                    "rr": round(risk_reward_value, 2),
                    "price_distance": round(tp_distance_value, 2),
                    "price": price,
                }
            ]
        return tiers

    tp_tiers = _build_tp_tiers(
        strategy=strategy,
        sl_distance_value=sl_distance,
        tp_distance_value=tp_distance,
        risk_reward_value=risk_reward,
        entry_price_value=entry_price,
        signal_value=signal,
    )

    diagnostics = {
        "sl_distance": round(sl_distance, 2),
        "tp_distance": round(tp_distance, 2),
        "tp_tiers": tp_tiers,
        "risk_reward": round(risk_reward, 2),
        "stop_distance": round(sl_distance, 2),
        "dynamic_rr": round(risk_reward, 2),
        "reason": "STRUCTURE_STOP" if selected_source == "structure" else "ADAPTIVE_ATR",
        "selected_stop_source": selected_source,
        "structure_candidates": structure_candidates,
        "atr_distance": round(atr_value * sl_multiplier, 2),
        "regime_factor": round(_regime_factor(market_regime), 3),
        "quality_factor": round(quality_bias, 3),
        "confidence_factor": round(confidence_bias, 3),
        "lot_factor": round(lot_scale, 3),
        "session_factor": round(_session_factor(session), 3),
        "execution_factor": round(_execution_factor(execution_grade), 3),
        "atr": round(atr_value, 2),
        "market_regime": str(market_regime or "UNKNOWN"),
        "strategy": str(strategy or "UNKNOWN"),
        "session": str(session or "UNKNOWN"),
        "quality_score": round(float(quality_score or 0.0), 2),
        "confidence": round(float(confidence or 0.0), 2),
        "lot": round(float(lot or 0.0), 2),
        "structure_strength": round(float(structure_strength or 0.0), 2),
        "liquidity": round(float(liquidity or 0.0), 2),
        "volatility": round(float(volatility or 0.0), 2),
        "spread": round(float(spread or 0.0), 2),
        "execution_grade": str(execution_grade or "UNKNOWN"),
        "brain_factor": round(brain_ratio, 3),
        "dna_factor": round(dna_ratio, 3),
        "broker_stop_level": round(float(broker_stop_level or 0.0), 2),
        "broker_stop_fallback": round(float(broker_stop_fallback or 0.0), 2),
        "safety_floor": round(float(safety_floor), 2),
    }
    print(
        "📐 ADAPTIVE SL ENGINE"
        f" | ATR={diagnostics['atr']}"
        f" | Regime={diagnostics['market_regime']}"
        f" | Quality={diagnostics['quality_score']}"
        f" | Confidence={diagnostics['confidence']}"
        f" | Lot={diagnostics['lot']}"
        f" | Structure={diagnostics['structure_strength']}"
        f" | SelectedStop={diagnostics['selected_stop_source']}"
        f" | FinalSL={diagnostics['sl_distance']}"
        f" | DynamicRR={diagnostics['risk_reward']}"
        f" | FinalTP={diagnostics['tp_distance']}"
    )
    return diagnostics
