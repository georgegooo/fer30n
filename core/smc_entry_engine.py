# =========================================
# FER3ON V5.7 — SMC ENTRY ENGINE V4
# Sweep + BOS + FVG/OB + Retest مع score bands حقيقية
# =========================================

from core.mt5_compat import mt5, MT5_AVAILABLE
from core.smart_money import (
    detect_liquidity_sweep,
    detect_bos,
    detect_fvg,
    detect_order_block,
)
from core.smc_advanced import analyze_smc_advanced


ENTRY_GRADE_SCORE = {
    "A+": 96,
    "A": 88,
    "B+": 79,
    "B": 70,
    "C": 57,
    "NONE": 0,
}

ENTRY_GRADE_BONUS = {
    "A+": 22,
    "A": 18,
    "B+": 14,
    "B": 10,
    "C": 4,
    "NONE": 0,
}


# =========================================
# HELPERS
# =========================================


def _inside_zone(price, zone):
    if not zone:
        return False
    try:
        zone_bot, zone_top = zone
        low = min(zone_bot, zone_top)
        high = max(zone_bot, zone_top)
        return low <= price <= high
    except Exception:
        return False



def get_entry_grade_score(grade):
    return ENTRY_GRADE_SCORE.get(str(grade or "NONE").upper(), 0)



def get_entry_grade_bonus(grade):
    return ENTRY_GRADE_BONUS.get(str(grade or "NONE").upper(), 0)


def should_allow_smc_entry(confirmed, grade):
    """Legacy-compatible soft gate for unified decision flow."""
    if bool(confirmed):
        return True
    return str(grade or "NONE").upper() in {"C", "NONE"}


def _grade_smc(details):
    sweep = bool(details["sweep"])
    bos = bool(details["bos"])
    fvg = bool(details["fvg"])
    ob = bool(details["ob"])
    mitigation = bool(details.get("mitigation"))
    breaker = bool(details.get("breaker"))
    pd_aligned = bool(details.get("premium_discount_aligned"))
    retest = bool(details["retest"])
    zone_present = fvg or ob or mitigation or breaker

    score = 0
    if sweep:
        score += 22
    if bos:
        score += 24
    if fvg:
        score += 18
    if ob:
        score += 14
    if mitigation:
        score += 14
    if breaker:
        score += 12
    if pd_aligned:
        score += 8
    if retest:
        score += 16

    if sweep and bos and zone_present:
        score += 8
    if zone_present and retest:
        score += 6
    if fvg and (ob or mitigation or breaker):
        score += 4

    score = min(score, 100)

    if sweep and bos and fvg and retest and pd_aligned:
        grade = "A+"
        confirmed = True
    elif sweep and bos and zone_present and retest:
        grade = "A"
        confirmed = True
    elif zone_present and retest and (sweep or bos):
        grade = "B+"
        confirmed = True
    elif zone_present and (sweep or bos or pd_aligned):
        grade = "B"
        confirmed = True
    elif sweep or bos or zone_present:
        grade = "C"
        confirmed = False
    else:
        grade = "NONE"
        confirmed = False

    score = max(score, get_entry_grade_score(grade)) if grade != "NONE" else score
    return confirmed, grade, min(score, 100)


# =========================================
# SMC ENTRY SEQUENCE
# =========================================


def check_smc_entry_sequence(symbol, signal):
    """
    يتحقق من تسلسل الدخول الاحترافي الكامل:
      1. Liquidity Sweep (H1)
      2. BOS (H1)
      3. FVG أو OB (M5)
      4. Retest داخل منطقة FVG/OB

    V5.7:
      - grade score واضح ومقروء
      - B+ تمثل band حقيقي ~79
      - الخصم لم يعد ينسف التقييم بالكامل
    """
    rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 60)
    rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 120)
    rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 60)

    if rates_h1 is None or rates_m5 is None or rates_m15 is None:
        return False, "NONE", {}

    details = {
        "sweep": False,
        "bos": False,
        "fvg": False,
        "ob": False,
        "mitigation": False,
        "breaker": False,
        "premium_discount_aligned": False,
        "retest": False,
        "grade": "NONE",
        "grade_score": 0,
        "fvg_zone": None,
        "ob_zone": None,
        "mitigation_zone": None,
        "breaker_zone": None,
        "premium_discount_zone": "NEUTRAL",
        "advanced_score": 0,
    }

    sweep = detect_liquidity_sweep(rates_h1, 20)
    if signal == "BUY" and sweep == "BUY_SWEEP":
        details["sweep"] = True
    elif signal == "SELL" and sweep == "SELL_SWEEP":
        details["sweep"] = True

    bos = detect_bos(rates_h1, 15)
    if signal == "BUY" and bos == "BOS_UP":
        details["bos"] = True
    elif signal == "SELL" and bos == "BOS_DOWN":
        details["bos"] = True

    fvg_sig, fvg_zone = detect_fvg(rates_m5, 18)
    if signal == "BUY" and "BUY" in str(fvg_sig):
        details["fvg"] = True
        details["fvg_zone"] = fvg_zone
    elif signal == "SELL" and "SELL" in str(fvg_sig):
        details["fvg"] = True
        details["fvg_zone"] = fvg_zone

    ob_sig, ob_zone = detect_order_block(rates_m5, 40)
    if signal == "BUY" and "BUY" in str(ob_sig):
        details["ob"] = True
        details["ob_zone"] = ob_zone
    elif signal == "SELL" and "SELL" in str(ob_sig):
        details["ob"] = True
        details["ob_zone"] = ob_zone

    advanced = analyze_smc_advanced(rates_h1, rates_m5, signal=signal)
    pd_zone = advanced.get("premium_discount", {}).get("zone", "NEUTRAL")
    details["premium_discount_zone"] = pd_zone
    details["premium_discount_aligned"] = (signal == "BUY" and pd_zone == "DISCOUNT") or (signal == "SELL" and pd_zone == "PREMIUM")

    if advanced.get("mitigation", {}).get("type") == f"{signal}_MITIGATION":
        details["mitigation"] = True
        details["mitigation_zone"] = advanced.get("mitigation", {}).get("zone")
    if advanced.get("breaker", {}).get("type") == f"{signal}_BREAKER":
        details["breaker"] = True
        details["breaker_zone"] = advanced.get("breaker", {}).get("zone")

    current_price = rates_m5[-1]["close"]
    if _inside_zone(current_price, details.get("fvg_zone")):
        details["retest"] = True
    if not details["retest"] and _inside_zone(current_price, details.get("ob_zone")):
        details["retest"] = True
    if not details["retest"] and _inside_zone(current_price, details.get("mitigation_zone")):
        details["retest"] = True
    if not details["retest"] and _inside_zone(current_price, details.get("breaker_zone")):
        details["retest"] = True

    details["advanced_score"] = round(
        advanced.get("buy_score", 0) if signal == "BUY" else advanced.get("sell_score", 0),
        2,
    )

    details["conditions_met"] = sum([
        details["sweep"],
        details["bos"],
        details["fvg"] or details["ob"] or details["mitigation"] or details["breaker"],
        details["retest"],
        details["premium_discount_aligned"],
    ])

    confirmed, grade, grade_score = _grade_smc(details)
    if details["advanced_score"] >= 5 and grade in ("B", "B+"):
        grade = "A" if grade == "B+" else "B+"
        grade_score = min(96, grade_score + 8)
    if details["premium_discount_aligned"] and grade != "NONE":
        grade_score = min(100, grade_score + 4)
    details["grade"] = grade
    details["grade_score"] = grade_score

    print(
        f"🎯 SMC_ENTRY | Sweep:{details['sweep']}"
        f" BOS:{details['bos']}"
        f" FVG:{details['fvg']}"
        f" OB:{details['ob']}"
        f" Mit:{details['mitigation']}"
        f" Brk:{details['breaker']}"
        f" PD:{details['premium_discount_zone']}"
        f" Retest:{details['retest']}"
        f" → Grade:{grade}"
        f" | Score:{grade_score}"
        f" | Adv:{details['advanced_score']}"
    )

    return confirmed, grade, details
