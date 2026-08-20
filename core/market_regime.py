# =========================================
# FER3ON V5.2 — MARKET REGIME
# الإصلاح: rates_h1 is not None بدل if rates_h1
# =========================================

from core.mt5_compat import mt5, MT5_AVAILABLE

from core.atr_manager import calculate_atr
from core.utils import calculate_ema
from core.settings import VOLATILE_MULT, CRISIS_MULT


def get_strategy_for_regime(regime):
    regime_key = str(regime or "UNKNOWN").upper()
    mapping = {
        "RANGING": "MICRO",
        "TRENDING": "SWING",
        "VOLATILE": "MICRO",
        "CRISIS": "RECOVERY",
        "UNKNOWN": "MICRO",
    }
    return mapping.get(regime_key, "MICRO")


# =============================================================================
# V7 — REGIME STRATEGY WEIGHTS (مرن، غير ثنائي، لا حظر)
# =============================================================================
# get_strategy_for_regime() أعلاه (V3.5 الأصلية) ثنائية صلبة — "regime واحد
# = استراتيجية واحدة فقط"، وهذا تعيين كان سيعني عمليًا إيقاف 3 من 4
# استراتيجيات بالكامل حسب حالة السوق، يخالف فلسفة "لا حظر، مرونة، أوزان"
# المتفَق عليها. لهذا لم تُستخدَم فعليًا في main.py حتى الآن (تأكَّد بالفحص).
#
# REGIME_STRATEGY_FIT أدناه يُعطي كل استراتيجية معامل توافق (0.5–1.15) مع كل
# حالة سوق، بدل تعيين ثنائي. يُستهلك كـ regime_fit_multiplier إضافي في
# core/trade_executor.py (نفس نقطة الالتقاء V6/V7) — كل الاستراتيجيات تبقى
# نشطة دائمًا، فقط حجمها يتكيف مع ملاءمتها لحالة السوق الحالية.
# القيم مبنية على المنطق التداولي المعروف: SCALP/MICRO تناسب RANGING بشكل
# أكبر (حركة محدودة المدى، صفقات سريعة)، DAILY/SWING تناسب TRENDING (تحتاج
# امتدادًا في الاتجاه)، الجميع يُصغَّر بحذر عند VOLATILE/CRISIS (لا يُمنع).
# =============================================================================

REGIME_STRATEGY_FIT = {
    "TRENDING": {"DAILY": 1.15, "SWING": 1.15, "SMC": 1.05, "SCALP": 0.90, "MICRO": 0.85},
    "RANGING":  {"DAILY": 0.80, "SWING": 0.80, "SMC": 0.95, "SCALP": 1.10, "MICRO": 1.10},
    "VOLATILE": {"DAILY": 0.70, "SWING": 0.70, "SMC": 0.85, "SCALP": 0.75, "MICRO": 0.80},
    "CRISIS":   {"DAILY": 0.50, "SWING": 0.50, "SMC": 0.60, "SCALP": 0.55, "MICRO": 0.60},
    "UNKNOWN":  {"DAILY": 1.00, "SWING": 1.00, "SMC": 1.00, "SCALP": 1.00, "MICRO": 1.00},
}


def get_regime_fit_multiplier(strategy, regime):
    """
    يُرجع معامل توافق الاستراتيجية مع حالة السوق الحالية — لا حظر أبدًا،
    فقط تصغير/تكبير محدود (نطاق القيم في REGIME_STRATEGY_FIT بين 0.50 و1.15).
    قيمة افتراضية آمنة 1.0 لأي استراتيجية أو regime غير معروف.
    """
    strat_key = str(strategy or "").upper()
    regime_key = str(regime or "UNKNOWN").upper()
    regime_table = REGIME_STRATEGY_FIT.get(regime_key, REGIME_STRATEGY_FIT["UNKNOWN"])
    return float(regime_table.get(strat_key, 1.0))


def detect_market_regime(symbol):
    rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
    if rates_m15 is None or len(rates_m15) < 10:
        return "UNKNOWN"

    atr = calculate_atr(rates_m15)

    rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 50)
    avg_atr = atr
    if rates_h1 is not None and len(rates_h1) > 10:
        avg_atr = sum(c["high"] - c["low"] for c in rates_h1) / len(rates_h1)

    crisis_thresh = round(avg_atr * CRISIS_MULT, 2)
    volatile_thresh = round(avg_atr * VOLATILE_MULT, 2)

    print(
        f"📊 REGIME | M15_ATR:{atr:.2f}"
        f" H1_AVG:{avg_atr:.2f}"
        f" | CRISIS>{crisis_thresh}"
        f" VOLATILE>{volatile_thresh}"
    )

    if atr > avg_atr * CRISIS_MULT:
        print("🚨 REGIME: CRISIS")
        return "CRISIS"

    if atr > avg_atr * VOLATILE_MULT:
        print("⚠️  REGIME: VOLATILE")
        return "VOLATILE"

    closes = [c["close"] for c in rates_m15]
    ema_fast = calculate_ema(closes, 20)
    ema_slow = calculate_ema(closes, 50)
    trend_strength = abs(ema_fast - ema_slow)

    if trend_strength > atr * 0.8:
        direction = "UP" if ema_fast > ema_slow else "DOWN"
        print(f"📈 REGIME: TRENDING ({direction})")
        return "TRENDING"

    print("↔️  REGIME: RANGING")
    return "RANGING"
