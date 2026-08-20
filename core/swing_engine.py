# =========================================
# FER3ON V4 — SWING ENGINE
# H4 Trend + London Breakout H1
# تُفعَّل في لندن أو نيويورك فقط
# =========================================

from core.mt5_compat import mt5, MT5_AVAILABLE
from datetime import datetime, timezone

from core.utils              import calculate_ema
from core.london_breakout    import get_london_breakout_signal
from core.settings           import (
    LONDON_START, LONDON_END,
    NY_START, NY_END
)


# =========================================
# SESSION CHECK — London أو NY
# =========================================

def is_swing_session():
    hour = datetime.now(timezone.utc).hour
    in_london = LONDON_START <= hour < LONDON_END
    in_ny     = NY_START     <= hour < NY_END
    return in_london or in_ny


# =========================================
# H4 TREND
# =========================================

def get_h4_trend(symbol):
    rates = mt5.copy_rates_from_pos(
        symbol, mt5.TIMEFRAME_H4, 0, 60
    )
    if rates is None or len(rates) < 50:
        return "NONE"

    closes   = [c['close'] for c in rates]
    ema_fast = calculate_ema(closes, 20)
    ema_slow = calculate_ema(closes, 50)

    if ema_fast > ema_slow:
        return "BUY"
    elif ema_fast < ema_slow:
        return "SELL"
    return "NONE"


# =========================================
# SWING SIGNAL
# =========================================

def get_swing_signal(symbol):
    """
    يشترط:
    1. جلسة لندن أو نيويورك
    2. H4 trend واضح
    3. London Breakout يؤكد
    """

    if not is_swing_session():
        return "NONE"

    # ——— H4 Trend ———
    h4_trend = get_h4_trend(symbol)
    if h4_trend == "NONE":
        print("⛔ SWING: H4 trend غير محدد")
        return "NONE"

    # ——— London Breakout ———
    lb_signal = get_london_breakout_signal(symbol)

    print(
        f"🌊 SWING | H4:{h4_trend}"
        f" | London:{lb_signal}"
    )

    if lb_signal != "NONE" and lb_signal == h4_trend:
        print(f"🚀 SWING SIGNAL: {lb_signal}")
        return lb_signal

    print("⛔ SWING: H4 وLondon غير متوافقين")
    return "NONE"
