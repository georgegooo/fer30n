# =========================================
# FER3ON MICRO TRADING ENGINE — V3.5
# High-frequency low-risk gold scalping
#
# V3.5 STABILIZATION:
#   1. Soft stricter thresholds (+10%) — Confidence 35/40, Score 60/65
#   2. Candle Confirmation: REJECTION / INSIDE BAR / MOMENTUM BREAKOUT
#      لا تظهر إلا بعد شمعتين متتاليتين بنفس الاتجاه.
#   3. لا نزعج / لا نخنق — الهدف إدخال فرص حقيقية فقط بدل كل نبضة.
# =========================================


def _body(candle):
    return abs(candle.get("close", 0) - candle.get("open", 0))


def _range(candle):
    return candle.get("high", 0) - candle.get("low", 0)


def _is_bullish(candle) -> bool:
    return candle.get("close", 0) > candle.get("open", 0)


def _is_bearish(candle) -> bool:
    return candle.get("close", 0) < candle.get("open", 0)


def _two_bar_confirmation(rates, required_direction):
    """
    Returns True only if there are TWO consecutive bars in required_direction,
    OR if last bar confirms a strong pattern (large body, body_ratio>=0.55).

    Required for: REJECTION / INSIDE BAR / MOMENTUM BREAKOUT patterns.
    Prevents acting on every single noise bar.
    """
    if rates is None or len(rates) < 3:
        return False

    prev2 = rates[-3]
    prev1 = rates[-2]
    last  = rates[-1]

    if required_direction == "BUY":
        sequential_bullish = _is_bullish(prev1) and _is_bullish(last)
        last_body_ratio = _body(last) / _range(last) if _range(last) else 0.0
        confirmation_bar = sequential_bullish or last_body_ratio >= 0.6
        return confirmation_bar

    if required_direction == "SELL":
        sequential_bearish = _is_bearish(prev1) and _is_bearish(last)
        last_body_ratio = _body(last) / _range(last) if _range(last) else 0.0
        confirmation_bar = sequential_bearish or last_body_ratio >= 0.6
        return confirmation_bar

    return False


def evaluate_micro_setup(rates, context=None):
    """
    V3.5 stabilized MICRO eval.
    Reads from core.settings — if MICRO_STABILIZATION_ACTIVE is True,
    applies +10% stricter thresholds and the 2-bar candle confirmation gate.
    """
    try:
        from core.settings import (
            MICRO_STABILIZATION_ACTIVE,
            MICRO_MIN_CONFIDENCE_DEFAULT,
            MICRO_MIN_SCORE_DEFAULT,
            CANDLE_CONFIRMATION_ENABLED,
            CANDLE_CONFIRMATION_REQUIRE_2_BARS,
            MICRO_EMA_DIRECTION_BONUS_ENABLED,
            MICRO_EMA_DIRECTION_BONUS_POINTS,
            MICRO_EMA_DIRECTION_VETO_ENABLED,
        )
    except Exception:
        MICRO_STABILIZATION_ACTIVE = False
        MICRO_MIN_CONFIDENCE_DEFAULT = 35
        MICRO_MIN_SCORE_DEFAULT = 55
        CANDLE_CONFIRMATION_ENABLED = False
        CANDLE_CONFIRMATION_REQUIRE_2_BARS = False
        MICRO_EMA_DIRECTION_BONUS_ENABLED = False
        MICRO_EMA_DIRECTION_BONUS_POINTS = 2
        MICRO_EMA_DIRECTION_VETO_ENABLED = False

    context = context or {}
    if rates is None or len(rates) < 2:
        return {
            "enabled": False,
            "direction": "NONE",
            "score": 0,
            "reasons": ["NO_DATA"],
        }

    prev = rates[-2]
    last = rates[-1]
    body = _body(last)
    rng = _range(last)
    body_ratio = body / rng if rng else 0.0
    upper = last.get("high", 0) - max(last.get("open", 0), last.get("close", 0))
    lower = min(last.get("open", 0), last.get("close", 0)) - last.get("low", 0)

    volume_spike = bool(context.get("volume_spike", False))
    liquidity_sweep = bool(context.get("liquidity_sweep", False))
    atr_expansion = bool(context.get("atr_expansion", False))
    breakout_strength = int(context.get("breakout_strength", 0) or 0)
    ema_direction = str(context.get("ema_direction") or context.get("EMA_DIRECTION") or "").upper()

    reasons = []
    score = 0

    # ------------------------ MOMENTUM DETECTION --------------------------
    bullish_break = last.get("close", 0) > prev.get("high", 0)
    bearish_break = last.get("close", 0) < prev.get("low", 0)

    if bullish_break and body_ratio >= 0.55:
        # Candidate BUY (will be confirmed via 2-bar gate if Req pattern)
        direction = "BUY"
        score += 2
        reasons.append("tick_momentum")
    elif bearish_break and body_ratio >= 0.55:
        direction = "SELL"
        score += 2
        reasons.append("tick_momentum")
    else:
        direction = "NONE"

    # ----------- CANDLE CONFIRMATION (Phase-1 V3.5) -----------------------
    # REJECTION / INSIDE BAR / MOMENTUM BREAKOUT لا تعتمد على شمعة واحدة.
    if CANDLE_CONFIRMATION_ENABLED and CANDLE_CONFIRMATION_REQUIRE_2_BARS:
        if direction in ("BUY", "SELL"):
            # Check tick_momentum pattern (this is a Momentum Breakout).
            if "tick_momentum" in reasons:
                if not _two_bar_confirmation(rates, direction):
                    reasons.append("tick_momentum_REJECTED_no_2bar_confirm")
                    # demote: لا تهلوس على شمعة واحدة
                    score = max(0, score - 2)
                    direction = "NONE"

    # ------------------------ CONTEXT BOOSTS ------------------------------
    if liquidity_sweep:
        score += 2
        reasons.append("liquidity_sweep")

    if MICRO_EMA_DIRECTION_BONUS_ENABLED and ema_direction in ("BUY", "SELL"):
        if direction == ema_direction:
            score += int(MICRO_EMA_DIRECTION_BONUS_POINTS)
            reasons.append("EMA_DIRECTION_BONUS")
        elif MICRO_EMA_DIRECTION_VETO_ENABLED and direction != "NONE":
            reasons.append("EMA_DIRECTION_BLOCK")
            score = max(0, score - 3)

    if volume_spike:
        score += 1
        reasons.append("volume_burst")
    if atr_expansion:
        score += 1
        reasons.append("atr_expansion")
    if breakout_strength >= 2:
        score += 1
        reasons.append("micro_bos")

    # --------------------- REJECTION (with confirmation) -------------------
    # Rejection now requires 2-bar confirmation per V3.5.
    if lower >= body * 1.8 and body_ratio >= 0.22:
        if (not CANDLE_CONFIRMATION_ENABLED
                or _two_bar_confirmation(rates, "BUY")):
            score += 1
            reasons.append("rejection_buy")
        else:
            reasons.append("rejection_buy_BLOCKED_no_2bar_confirm")

    if upper >= body * 1.8 and body_ratio >= 0.22:
        if (not CANDLE_CONFIRMATION_ENABLED
                or _two_bar_confirmation(rates, "SELL")):
            score += 1
            reasons.append("rejection_sell")
        else:
            reasons.append("rejection_sell_BLOCKED_no_2bar_confirm")

    # ----------------- STRICTER SCORE THRESHOLD (+10%) ---------------------
    if MICRO_STABILIZATION_ACTIVE:
        micro_score_threshold = MICRO_MIN_SCORE_DEFAULT  # 60
    else:
        micro_score_threshold = 55

    score_percent = min(100, score * 10)
    if score_percent < micro_score_threshold:
        reasons.append(f"SCORE_BELOW_{micro_score_threshold}")
        return {
            "enabled": False,
            "direction": "NONE",
            "score": score,
            "score_percent": score_percent,
            "reasons": reasons,
        }

    return {
        "enabled": True,
        "direction": direction,
        "score": score,
        "score_percent": score_percent,
        "reasons": reasons,
        "recovery_entry": bool(context.get("recovery_entry", False)),
        "v3_5_marker": "STABILIZED_MICRO",
    }


def should_enter_micro(rates, context=None):
    """
    Returns (bool, dict).
    For V3.5 we ALSO check the confidence threshold (default 35 — old 30 was
    too noisy). The caller passes `context['confidence']` if it has one.
    """
    try:
        from core.settings import (
            MICRO_STABILIZATION_ACTIVE,
            MICRO_MIN_CONFIDENCE_DEFAULT,
        )
    except Exception:
        MICRO_STABILIZATION_ACTIVE = False
        MICRO_MIN_CONFIDENCE_DEFAULT = 35

    result = evaluate_micro_setup(rates, context=context)
    if not result.get("enabled", False):
        return False, result

    if MICRO_STABILIZATION_ACTIVE:
        confidence = float((context or {}).get("confidence", 100) or 0)
        if confidence < MICRO_MIN_CONFIDENCE_DEFAULT:  # 35
            result["reasons"].append(f"CONF_BELOW_{MICRO_MIN_CONFIDENCE_DEFAULT}")
            return False, result

    return True, result
