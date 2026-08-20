# =========================================
# FER3ON V3 — SCALPING ENGINE
# يدمج: EMA + RSI + Candle + S/R
#        + Daily Bias + MTF (إجباري)
# =========================================

from core.mt5_compat import mt5, MT5_AVAILABLE

from core.candle_patterns  import detect_candle_pattern
from core.ai_scoring       import calculate_trade_score
from core.utils            import calculate_ema
from core.multi_timeframe  import get_mtf_consensus, mtf_allows_trade
from core.daily.signal     import get_daily_bias
from core.settings         import MIN_SCORE_SCALP, MTF_REQUIRED


# =========================================
# RSI
# =========================================

def calculate_rsi(closes, period=14):

    gains, losses = [], []

    for i in range(1, len(closes)):
        chg = closes[i] - closes[i - 1]
        if chg > 0:
            gains.append(chg)
        else:
            losses.append(abs(chg))

    if not gains:
        return 0
    if not losses:
        return 100

    avg_g = sum(gains[-period:]) / period
    avg_l = sum(losses[-period:]) / period

    if avg_l == 0:
        return 100

    return 100 - (100 / (1 + avg_g / avg_l))


# =========================================
# SUPPORT / RESISTANCE
# =========================================

def support_resistance(rates, lookback=30):

    highs = [c['high'] for c in rates[-lookback:]]
    lows  = [c['low']  for c in rates[-lookback:]]

    return min(lows), max(highs)


# =========================================
# SCALPING SIGNAL
# =========================================

def get_scalping_signal(symbol):

    rates = mt5.copy_rates_from_pos(
        symbol, mt5.TIMEFRAME_M5, 0, 100
    )

    if rates is None:
        return "NONE"

    closes = [c['close'] for c in rates]
    price  = closes[-1]

    # ===================================
    # EMA TREND (M5)
    # ===================================
    ema_fast = calculate_ema(closes, 9)
    ema_slow = calculate_ema(closes, 21)

    if ema_fast > ema_slow:
        ema_trend = "BUY"
    elif ema_fast < ema_slow:
        ema_trend = "SELL"
    else:
        print("⛔ EMA: لا اتجاه واضح")
        return "NONE"

    # ===================================
    # RSI
    # ===================================
    rsi = calculate_rsi(closes)

    # ===================================
    # SUPPORT / RESISTANCE
    # ===================================
    support, resistance = support_resistance(rates)

    # ===================================
    # CANDLE PATTERN
    # ===================================
    candle = detect_candle_pattern(rates)

    # ===================================
    # DAILY BIAS — إجباري
    # ===================================
    daily_bias = get_daily_bias(symbol)

    # تعارض Daily Bias → رفض فوري
    if daily_bias != "NONE" and daily_bias != ema_trend:
        print(
            f"❌ DAILY BIAS CONFLICT:"
            f" {daily_bias} vs EMA:{ema_trend}"
        )
        return "NONE"

    # ===================================
    # MTF CONSENSUS — إجباري
    # ===================================
    if MTF_REQUIRED:
        mtf_ok, mtf_data = mtf_allows_trade(
            symbol, ema_trend
        )
        if not mtf_ok:
            return "NONE"

        mtf_dir      = mtf_data["direction"]
        mtf_strength = mtf_data["strength"]
    else:
        mtf_dir, mtf_strength = ema_trend, 1

    # ===================================
    # AI SCORING
    # ===================================
    score, reasons = calculate_trade_score(
        ema_trend     = ema_trend,
        rsi           = rsi,
        candle_signal = candle,
        current_price = price,
        support       = support,
        resistance    = resistance,
        daily_bias    = daily_bias,
        mtf_direction = mtf_dir,
        mtf_strength  = mtf_strength
    )

    # ===================================
    # DEBUG
    # ===================================
    print(
        f"⚡ EMA {ema_fast:.1f}/{ema_slow:.1f}"
        f" | RSI:{rsi:.1f}"
        f" | Candle:{candle}"
        f" | DailyBias:{daily_bias}"
        f" | Score:{score}/{MIN_SCORE_SCALP}"
    )
    print(f"📋 {reasons}")

    # ===================================
    # FINAL DECISION — threshold رُفع 5→6
    # ===================================
    if score >= MIN_SCORE_SCALP and ema_trend == "BUY":
        print("🚀 SCALP BUY — HIGH CONFIDENCE")
        return "BUY"

    elif score >= MIN_SCORE_SCALP and ema_trend == "SELL":
        print("🚀 SCALP SELL — HIGH CONFIDENCE")
        return "SELL"

    print(
        f"⛔ LOW CONFIDENCE (score={score}"
        f" < {MIN_SCORE_SCALP})"
    )
    return "NONE"
