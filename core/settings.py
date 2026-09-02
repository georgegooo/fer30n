# =============================================================================
# FER3ON AI V3-FIXED — INSTITUTIONAL PERSONAL AI TRADING SYSTEM (XAUUSD)
# =============================================================================
# الفلسفة الموحدة:
#   1) Capital Protection First   (hard caps لا تُمس)
#   2) Single Decision Authority  (Unified Decision Engine هو الحَكَم الوحيد)
#   3) No Engine Deletion          (كل أركان V6/V7 موجودة كـ Evidence Producers)
#   4) Layered Execution           (FULL / REDUCED / MICRO / HARD_BLOCK)
#   5) Trade Smart in Hard Times   (Micro/Reduced بدل الجمود الكامل)
#   6) Learn After Outcome         (التعلم بعد النتيجة لا قبلها فقط)
# =============================================================================
# تركيب الإصدار:
#   - مبني على FER3ON V2.2 OPERATIONAL
#   - مُصحح: stop distance calculation
#   - مُعدّل: حساب 1000$ — lot sizing مناسب
#   - مُفتّح: 80 صفقة يومياً بدل 8
# =============================================================================

import os

from config.ai_config import AI_CONFIG
from config.execution_config import EXECUTION_CONFIG

SYMBOL    = 'XAUUSD'
TIMEFRAME = 15
BOT_NAME    = 'FER3ON-AI-V3-PLUS-PLUS-PLUS'
BOT_VERSION = '3.0.3-FER3ON-AI-V3-PLUS-PLUS-PLUS'
BOT_TAGLINE = 'Real-Ready Edition — RR=1:2 + 60T/Day + 1.5% Risk'

# =============================================================================
# BUILD IDENTITY — stamped onto every trade record written from this point on
# =============================================================================
# Root-cause fix for a data-integrity finding: trade records from the three
# retired pre-merge versions (and at least one untagged data-merge artifact —
# 57 rows in data/history/trades.csv with blank ticket/strategy, replayed
# with the current-run timestamp instead of their original one) were being
# read by certification/framework.py and analytics code with no way to tell
# them apart from real trades produced by THIS build's logic. That made
# certification_status.md's "77 closed trades, WR 54.55%" a blend of retired
# strategy versions and the current build — not a measurement of anything
# currently running.
#
# BUILD_ID is written into every new row this build produces (trade_executor
# open-time log, mt5_history_sync close-time sync, truth_layer TradeRecord).
# Anything without a matching BUILD_ID — including all pre-existing rows,
# which get backfilled to a LEGACY_* label rather than this value — is
# excluded from certification/analytics going forward by construction,
# instead of relying on every downstream script remembering to filter by
# date.
BUILD_ID = 'FER3ON-FINAL-build1-MERGED-rearch-cert6'
BUILD_DEPLOYED_AT = '2026-08-19T15:41:47+00:00'
# NOTE: BUILD_ID was static at 'FER3ON-FINAL-build1' from the original
# 2026-07-27 deployment all the way through the mid-August audit/hardening
# cycle and the REARCH+CERT6 merge -- it was never bumped across any of
# those changes. That meant certification/health filtering by build_id
# (certification/framework.py, analytics/quant_engine.py strategy health,
# core/mt5_history_sync.py, tools/fix_truth_layer_ticket_keys.py) was
# filtering against a value nothing was ever excluded by, since every row
# logged since 2026-07-27 -- including trades made before the ticket-key
# dedup fix, the tp_monitor magic-field fix, the ATR/SL-unit fix, and while
# MICRO was still enabled -- carried the same identical build_id. Bumping
# it here on the REARCH+CERT6 merge is what actually activates the
# quarantine-by-build_id mechanism described above for the first time.
# Bump this again (and update BUILD_DEPLOYED_AT) on the next structural
# merge so this doesn't silently go stale a second time.

# =============================================================================
# ACCOUNT CONFIG — frozen single profile for a $200-$1000 real account
# =============================================================================
# FER3ON FINAL — FROZEN PRODUCTION CONFIG (merge build, see
# FER3ON_FINAL_CHANGELOG.md items [SETTINGS-1] and [SLTP-2]).
#
# The previous 3-tier account-size system (small/medium/large, auto-selected
# from a guessed BASE_ACCOUNT_BALANCE) has been replaced with ONE explicit
# profile, calibrated for a real balance in the $200-$1000 range as
# confirmed by the account owner. This removes the config-ambiguity danger
# entirely rather than just capping it (see [SETTINGS-1] history below).
#
# WHY THESE SPECIFIC NUMBERS (see [SLTP-2] for the full derivation):
# XAUUSD's broker-minimum lot (0.01 = 1oz) means every trade risks at least
# $1 per $1 of stop distance, with no way to size smaller. A realistic
# ATR-based gold stop is commonly $1-3 — at MIN_LOT that alone is
# $1-3 of risk, which is 15-45% of a $200 balance. No risk_percent setting
# can fix this by itself; the stop distance itself must be bounded for an
# account this size. MAX_SL_DISTANCE_DOLLARS below does that, and
# RISK_PER_TRADE_PERCENT is set to a realistic value given that bound,
# rather than a textbook 0.5-1% that this lot granularity cannot actually
# deliver. core/risk_manager.py::calculate_smart_lot's MIN_LOT_RISK_GUARD
# is the final backstop that skips a trade outright if even the capped
# stop would blow past a sane multiple of intended risk.
# =============================================================================
_ACCOUNT_MODE = (os.getenv('ACCOUNT_MODE', 'DEMO') or 'DEMO').upper()
_ACCOUNT_BALANCE_ENV = os.getenv('ACCOUNT_BALANCE_USD')
_IS_REAL_MODE = _ACCOUNT_MODE in {'REAL', 'LIVE', 'LIVE_TRADING'}

if _ACCOUNT_BALANCE_ENV is not None:
    BASE_ACCOUNT_BALANCE = max(1.0, float(_ACCOUNT_BALANCE_ENV))
elif _IS_REAL_MODE:
    # REAL mode with no explicit balance → fail SAFE to the low end of the
    # confirmed $200-$1000 range rather than guessing higher.
    print(
        '⚠️ ACCOUNT_MODE=REAL but ACCOUNT_BALANCE_USD is not set — '
        'defaulting to $200 (the conservative low end of your range). '
        'Set ACCOUNT_BALANCE_USD explicitly to your real balance.'
    )
    BASE_ACCOUNT_BALANCE = 200.0
else:
    # DEMO default — no real capital at risk either way.
    BASE_ACCOUNT_BALANCE = 1000.0

RISK_PER_TRADE_PERCENT = 0.75     # conservative low-account profile for XAUUSD; keeps MIN_LOT risk tractable
# FER3ON FINAL [EXPOSURE-3]: floor for any confidence/strategy-scaled
# risk_percent derived from RISK_PER_TRADE_PERCENT below (main.py's
# risk_multiplier scaling, strategy_runners.py's BASE_RISK_*). Without a
# floor tied to RISK_PER_TRADE_PERCENT, those independent scaling formulas
# could (and did, before this fix) drift low enough that MIN_LOT's implied
# risk always exceeded MIN_LOT_RISK_MULTIPLE_CAP, silently skipping every
# single trade at the $200 end of the range. See FER3ON_FINAL_CHANGELOG.md
# [EXPOSURE-3] for the full trace.
MIN_EFFECTIVE_RISK_PERCENT = 0.75
MAX_RISK_PER_DAY_PERCENT = 5.0   # unified daily loss brake for all risk paths
MAX_LOT = 0.06                   # tighter ceiling for safer execution in low-balance accounts
MIN_LOT = 0.01                   # broker floor for XAUUSD (1oz)
MIN_SL_DISTANCE = 500.0          # last-resort floor ($5) — only used if ATR computation fails entirely
BROKER_STOP_LEVEL_FALLBACK = 50  # ~$0.50 fallback when broker doesn't report trade_stops_level
MAX_RISK_TOTAL = 1.5             # ceiling on risk_percent itself (calculate_smart_lot clamps to this)

# Absolute ceilings — kept as a defensive backstop even though there is only
# one profile now, so a future edit above can't silently exceed the FINAL
# build's safety envelope (Action Plan #1, #4, #5).
MAX_LOT = min(MAX_LOT, 0.10)
MAX_RISK_PER_DAY_PERCENT = min(MAX_RISK_PER_DAY_PERCENT, 5.0)

# =============================================================================
# FER3ON FINAL — MIN-LOT RISK GUARD (new, build spec bonus fix [SLTP-2])
# On a small account, the broker's MIN_LOT (0.01) can represent MORE dollar
# risk than the intended risk_percent once multiplied by a realistic
# ATR-based gold stop (e.g. 0.01 lot × $30 stop = $0.30 loss — 15% of a $200
# balance, versus an intended 0.75%). core/risk_manager.py::calculate_smart_lot
# now compares the risk actually implied by MIN_LOT against the intended
# risk_amount; if it exceeds this multiple, the trade is SKIPPED instead of
# silently opened at an oversized relative risk. Set to a high number
# (e.g. 999) to disable and always force MIN_LOT as before.
#
# MAX_SL_DISTANCE_DOLLARS caps the adaptive engine's stop distance itself
# (applied in core/trade_executor.py::_enforce_min_stop_distance and
# core/strategy_runners.py's order builder) — without this, a volatile-
# session ATR spike could produce a $100+ stop that MIN_LOT_RISK_MULTIPLE_CAP
# would just skip forever; capping the stop directly keeps trades flowing
# while keeping worst-case single-trade risk bounded at MIN_LOT. With the
# conservative small-account profile used here, a slightly higher cap is
# required so the system can still trade at 0.75% base risk without
# rejecting every min-lot setup on a $200 account.
# =============================================================================
# =============================================================================
# FER3ON-FIX-2026-08-19 [CAPITAL-PROTECTION-1] — strict small-account stop cap
# Per the audit report: on balances < $500, a $30 stop at MIN_LOT = 15-45% of
# the account per trade. The stop-distance cap is now balance-dependent:
#   balance >= $500 → $30 (unchanged FINAL behaviour)
#   balance <  $500 → $15 hard cap (worst-case MIN_LOT risk = 7.5% of $200)
# Override via MAX_SL_DISTANCE_DOLLARS env var if you accept the higher risk.
# =============================================================================
# =============================================================================
# FER3ON-FIX-2026-08-28 [CAPITAL-PROTECTION-2] — flatten to $15 hard cap
# القرار المعلّق من كذا نقاش: وثيقتين (Future Improvement Roadmap و"أفضل
# فكرة للـSL/TP") حددوا SL_HARD_LIMIT=$15 صراحةً لمرحلة الاختبار الحالية
# ("ممنوع السماح بـ$30 أو $50 كـSL فعلي")، بينما الإعداد كان لسه $30
# لحساب ≥$500. اتغيّر لـ$15 لكل الأحجام دلوقتي — الفرع أدناه اتسيب زي ما
# هو (تدرّج حسب الرصيد) لسهولة الرجوع لاحقًا لو احتجتوا تدرّج مختلف.
# =============================================================================
_MAX_SL_ENV = os.getenv('MAX_SL_DISTANCE_DOLLARS')
if _MAX_SL_ENV is not None:
    MAX_SL_DISTANCE_DOLLARS = max(1.0, float(_MAX_SL_ENV))
else:
    MAX_SL_DISTANCE_DOLLARS = 15 if BASE_ACCOUNT_BALANCE >= 500.0 else 15
TOTAL_RISK_CAP = float(MAX_SL_DISTANCE_DOLLARS)
MIN_LOT_RISK_MULTIPLE_CAP = 8.0 if BASE_ACCOUNT_BALANCE >= 500.0 else 5.0

# =============================================================================
# FER3ON-FIX-2026-08-19 [QUALITY-INVERSION-1] — quality_score trust switch
# Data-proven inversion: on 120 real closed trades, losers averaged
# quality_score 55.5 vs winners 35.6 — the score currently filters OUT good
# trades and lets bad ones through. Until the score is recalibrated against
# post-FIX trade data (min 50 new trades), the quality gate must NOT be the
# entry authority. With QUALITY_SCORE_TRUST_ENABLED=False, evaluate_quality_gate
# approves pass-through and entry authority rests on the kill-switch +
# expected-edge gate only. Flip back to True ONLY after recalibration shows
# a positive correlation between quality_score and realized profit.
# =============================================================================
QUALITY_SCORE_TRUST_ENABLED = os.getenv('QUALITY_SCORE_TRUST', 'False').strip().lower() in {'1', 'true', 'yes', 'on'}


def get_min_sl_dollars(point: float = 0.01) -> float:
    """Canonical floor for stop-loss distance, in raw price dollars.

    [REARCH-1] Single source of truth for a formula that used to be
    reimplemented in two places that could silently drift apart:
      - core/strategy_runners.py had this exact expression copy-pasted as a
        literal at 6 call sites (one per strategy cycle / TP-ladder branch).
      - core/trade_executor.py::_enforce_min_stop_distance computed the same
        thing with the same inputs but written differently (`MIN_SL_DISTANCE
        * point` inline), because it has access to the live broker point
        value where strategy_runners.py does not.
    Both now call this function. `point` defaults to 0.01 because SYMBOL is
    always XAUUSD in this build ([SLTP-1] established that MIN_SL_DISTANCE is
    a "points" setting that must be converted to price-dollars before use);
    trade_executor.py passes the real broker point when it has one, exactly
    matching the original per-call-site behaviour this replaces — no trading
    logic changes, only where the formula lives. See docs/history/
    FER3ON_FINAL_CHANGELOG.md [SLTP-1] for the original bug this floor guards
    against.
    """
    return max(5.00, float(MIN_SL_DISTANCE) * point)


# =============================================================================
# CENTRALIZED CONFIG SHIM
# =============================================================================

CONFIDENCE_FLOOR = AI_CONFIG['confidence_floor']
CONFIDENCE_CEILING = AI_CONFIG['confidence_ceiling']
MAX_CONCURRENT_POSITIONS = EXECUTION_CONFIG['max_concurrent_positions']
MAX_DAILY_RISK = MAX_RISK_PER_DAY_PERCENT  # V3.5 unified — single source of truth

# =============================================================================
# V3.5 — OPEN POSITION LIMITS (Phase-1)
# كل استراتيجية بحد أقصى صفقة واحدة مفتوحة في نفس الوقت
# =============================================================================

MAX_OPEN_TRADES = 4
# FER3ON FINAL [EXPOSURE-2]: main.py's SMC path already checked live MT5
# positions for a same-direction concentration cap (hardcoded 4, matching
# MAX_OPEN_TRADES) — core/strategy_runners.py's SCALP/SWING/MICRO paths did
# not have the equivalent check. Named here so both paths can share one
# number instead of two independently-hardcoded 4s drifting apart.
MAX_SAME_DIRECTION_POSITIONS = 4
MAX_OPEN_PER_STRATEGY = 1
MAX_OPEN_SCALP = 1
MAX_OPEN_MICRO = 1
MAX_OPEN_SMC   = 1
MAX_OPEN_SWING_OR_DAILY = 1   # SWING و DAILY يتقاسمان نفس الحد الأقصى

# [REARCH-2] Per-strategy SOFT position-count ceilings, read by
# core/risk_manager.py::evaluate_position_limits. This used to be a second,
# separate hardcoded dict living inline inside risk_manager.py with no
# visibility from settings.py -- moved here so this file is genuinely the
# one place that defines position-count policy, alongside MAX_OPEN_TRADES
# and MAX_OPEN_PER_STRATEGY above. Values are unchanged from before this
# move. NOTE: with MAX_OPEN_TRADES=4 above, TOTAL is already the binding
# constraint for every strategy today -- none of these per-strategy numbers
# can currently be reached in practice. They only start to matter if
# MAX_OPEN_TRADES is raised later. SWING matches DAILY's cap since both are
# slower/longer-hold strategies relative to SCALP/MICRO (see AUDIT FIX note
# in FER3ON_FINAL_CHANGELOG.md for the original SWING/DAILY copy-paste bug
# this table also fixed).
PER_STRATEGY_SOFT_POSITION_LIMITS = {
    'SCALP': 20,
    'MICRO': 40,
    'DAILY': 10,
    'SWING': 10,
}

# Compatibility alias: legacy config consumers expect a RISK_CONFIG dict, but
# the project runtime must always read values from this module.
RISK_CONFIG = {
    'max_daily_risk': MAX_DAILY_RISK,
    'max_daily_risk_pct': MAX_RISK_PER_DAY_PERCENT,
    'max_risk_per_trade_pct': RISK_PER_TRADE_PERCENT,
    'max_open_trades': MAX_OPEN_TRADES,
    'max_day_loss_pct': MAX_RISK_PER_DAY_PERCENT,
    'max_position_risk': RISK_PER_TRADE_PERCENT,
    'max_drawdown': 0.08,
    'recovery_risk_multiplier': 0.5,
    'anti_revenge_loss_trigger': 2,
    'cooldown_after_loss': 300,
    'hard_stop_enabled': True,
    'survival_mode_enabled': True,
}

# =============================================================================
# MAGIC NUMBERS
# =============================================================================

SCALP_MAGIC = 1001
DAILY_MAGIC = 2001
SWING_MAGIC = 3001
SMC_MAGIC   = 4001
MICRO_MAGIC = 5001
# AUDIT FIX [RECOVERY_MAGIC/SURVIVAL_MAGIC]: RECOVERY and SURVIVAL had no
# registered magic numbers even though core/recovery_engine.py,
# core/survival_intelligence.py, core/meta_ai_orchestrator.py,
# core/dynamic_aggression.py and RECOVERY/SURVIVAL branches inside live files
# (core/risk_manager.py, core/candle_trigger.py) all reference those strategy
# names. No live path currently opens a trade with strategy='RECOVERY' or
# 'SURVIVAL' (main.py hardcodes 'SMC'; strategy_runners.py's cycles each pass
# their own fixed name), so this was inert -- but had any of those orphaned
# modules ever reached main.py, core.trade_identity.magic_from_strategy()
# would have had no entry for them and returned whatever magic the caller
# happened to pass as `fallback` (possibly 0, possibly another strategy's
# magic), silently breaking the per-strategy "one open trade" check in
# core/trade_executor.py (STEP 3, keyed by magic). Registering them here
# closes that gap defensively.
RECOVERY_MAGIC = 6001
SURVIVAL_MAGIC = 7001

# =============================================================================
# BASE RISK PER STRATEGY (%) — adaptive sizing is set above based on account size
# =============================================================================
# FER3ON FINAL [EXPOSURE-3]: previously independent hardcoded values
# (0.40-0.75%) with no connection to RISK_PER_TRADE_PERCENT above. On this
# account's $200-$1000 range, that meant every one of these was too small
# for core.risk_manager.calculate_smart_lot's MIN_LOT_RISK_GUARD ([SLTP-2])
# to ever pass at $200 — the guard would skip every single SCALP/SWING/MICRO
# trade, silently. Now anchored to the same single source of truth, with
# relative strategy differentiation preserved but floored at
# MIN_EFFECTIVE_RISK_PERCENT so none of them can silently stop trading at
# the low end of the confirmed balance range. See FER3ON_FINAL_CHANGELOG.md
# [EXPOSURE-3].
BASE_RISK_SCALP = max(MIN_EFFECTIVE_RISK_PERCENT, RISK_PER_TRADE_PERCENT * 1.0)
BASE_RISK_DAILY = max(MIN_EFFECTIVE_RISK_PERCENT, RISK_PER_TRADE_PERCENT * 0.9)
BASE_RISK_SWING = max(MIN_EFFECTIVE_RISK_PERCENT, RISK_PER_TRADE_PERCENT * 0.9)
BASE_RISK_SMC   = max(MIN_EFFECTIVE_RISK_PERCENT, RISK_PER_TRADE_PERCENT * 1.0)
BASE_RISK_MICRO = max(MIN_EFFECTIVE_RISK_PERCENT, RISK_PER_TRADE_PERCENT * 0.8)
MIN_TP_DISTANCE_MULT = 2.0    # RR = 1:2 كحد أدنى (TP ضعف SL)
MIN_RR_RATIO_V3 = 2.0         # حد أدنى صارم لـ RR في V3-FIXED

# =============================================================================
# FER3ON FINAL — ORDER STOPS-REJECTION RETRY (ported from V9FINAL1)
# "إذا رفض الوسيط الأمر بسبب قرب الوقف، أعد إرسال الطلب مع زيادة تدريجية
#  (مثل 10% في كل محاولة) حتى يقبله الوسيط"
# Wired into core/trade_executor.py::_send_order_with_stops_retry — see
# build spec Merge item #1 / FER3ON_FINAL_CHANGELOG.md [EXEC-1].
# =============================================================================
ORDER_RETRY_ON_STOPS_REJECTION_ENABLED = True
ORDER_RETRY_STEP_PCT = 0.10        # +10% على مسافة SL/TP في كل محاولة
ORDER_RETRY_MAX_ATTEMPTS = 5        # حد أقصى للمحاولات (حماية من حلقة لا نهائية)
# retcode الخاصة برفض "stops too close" في MT5 (موسَّعة لتغطية أكثر من broker)
ORDER_RETRY_REJECTION_RETCODES = (10016, 10017, 10006)

# FER3ON FINAL — STOPS-RETRY WIDENING CAP (Phase-0 hygiene, 2026-08)
# Without a cap, attempt #4 widens SL by 1.10^4 ≈ 1.61x ($30 → $48),
# silently multiplying real risk beyond the account-size cap the rest of
# the pipeline was built around. The cap is the TIGHTER of this factor
# and MAX_SL_DISTANCE_DOLLARS (enforced in core/trade_executor.py).
ORDER_RETRY_MAX_WIDEN_FACTOR = 1.30   # أقصى توسيع مسموح لمسافة SL عبر الـ retries

# FER3ON — PHASE 1 | SHADOW COUNTERFACTUAL (REJECTED_SHADOW ledger)
# Every rejected signal is logged as REJECTED_SHADOW and its hypothetical
# outcome is resolved later against real candles. LOGGING ONLY — nothing
# here is read back into the live decision path.
SHADOW_COUNTERFACTUAL_ENABLED       = True
ANALYTICS_DATA_EPOCH                = "2026-09-01-clean"
ANALYTICS_SCHEMA_VERSION            = "5.0"
SHADOW_COUNTERFACTUAL_LOG_PATH      = "data/analytics/shadow_counterfactual/rejected_shadow_2026-09-01-clean.jsonl"
SHADOW_COUNTERFACTUAL_QUARANTINE_PATH = "data/analytics/quarantine/rejected_shadow_invalid_2026-09-01-clean.jsonl"
SHADOW_COUNTERFACTUAL_HORIZON_BARS  = 48    # شموع المتابعة قبل اعتبار النتيجة TIMEOUT
SHADOW_COUNTERFACTUAL_MIN_SAMPLES   = 100   # الحد الأدنى قبل استخلاص أي استنتاج إحصائي

# =============================================================================
# FER3ON — PHASE 2 | ENTRY CONTROLLER + STRUCTURAL SL (Demo)
# =============================================================================
# Instead of entering at market the moment a signal fires, the controller
# plans a pullback LIMIT entry and a STRUCTURE-anchored SL (beyond the
# opposing swing + ATR buffer), hard-capped per strategy. Default mode is
# ADVISORY: plans are computed and logged, live orders are NOT changed until
# PHASE2_ENTRY_CONTROLLER_LIVE_ENABLED is explicitly switched on for Demo.
PHASE2_ENTRY_CONTROLLER_ENABLED        = True
PHASE2_ENTRY_CONTROLLER_LIVE_ENABLED   = False  # advisory/log-only حتى مراجعة الديمو
PHASE2_ENTRY_CONTROLLER_LOG_PATH       = "data/analytics/entry_controller/entry_plans_2026-09-01-clean.jsonl"
PHASE2_ENTRY_CONTROLLER_QUARANTINE_PATH = "data/analytics/quarantine/entry_plans_invalid_2026-09-01-clean.jsonl"
PULLBACK_DEPTH_ATR                     = 0.5    # عمق الارتداد لأمر الـ LIMIT = 0.5 × ATR
ENTRY_TTL_BARS                         = 6      # صلاحية أمر الارتداد قبل الإلغاء
STRUCTURAL_SL_ATR_BUFFER               = 0.3    # بفر خلف القاع/القمة البنيوية
STRUCTURAL_SL_CAP_SCALP                = 10.0   # سقف $10 للسكالب/الميكرو
STRUCTURAL_SL_CAP_SWING                = 15.0   # سقف $15 لـ SMC/SWING
PROACTIVE_OPPORTUNITY_SCAN_ENABLED     = True
PROACTIVE_OPPORTUNITY_SCAN_INTERVAL    = 5      # shadow scan every N heartbeats

# =============================================================================
# FER3ON — PHASE 3 | EXIT MANAGER (independent TP ladder + trailing + time exit, Demo)
# =============================================================================
# TP is derived from its own RR ladder (independent of how SL was built),
# exits are staged (partial closes), SL moves to breakeven after TP1 and
# trails by ATR after TP2, and a stale trade is closed after TIME_EXIT_BARS.
# Advisory/log-only until PHASE3_EXIT_MANAGER_LIVE_ENABLED is switched on.
PHASE3_EXIT_MANAGER_ENABLED            = True
PHASE3_EXIT_MANAGER_LIVE_ENABLED       = False  # advisory/log-only حتى مراجعة الديمو
PHASE3_EXIT_MANAGER_LOG_PATH           = "data/analytics/exit_manager/exit_actions.jsonl"
TP_LADDER_RR                           = (1.5, 2.5, 4.0)   # مستويات الهدف المستقلة بمضاعفات R
TP_LADDER_FRACTIONS                    = (0.5, 0.3, 0.2)   # نسب الإغلاق الجزئي لكل مستوى
BREAKEVEN_BUFFER_ATR                   = 0.1    # بفر فوق التعادل بعد TP1
TRAILING_ATR_MULT                      = 1.0    # مسافة التتبع بعد TP2 = 1 × ATR
TIME_EXIT_BARS                         = 24     # خروج زمني لو لا TP1 ولا SL خلال 24 شمعة

# =============================================================================
# LOSS-PAUSEGUARD — انتظار CHoCH/BOS جديد بعد صفقات خاسرة متتالية
# =============================================================================
LOSS_PAUSE_ENABLED        = True
LOSS_PAUSE_TRIGGER        = 2    # عدد الصفقات الخاسرة المتتالية لتشغيل الإيقاف
LOSS_PAUSE_REQUIRE_FRESH  = True # يجب ظهور CHoCH أو BOS جديد لتجاوز الإيقاف
LOSS_PAUSE_REQUIRE_REGIME = ('RANGING', 'VOLATILE','TRENDING', 'UNKNOWN')  # الإيقاف يعمل في هذه الـ regimes فقط
LOSS_PAUSE_COOLDOWN_SEC   = 300  # cooldown زمني بعد pause

# =============================================================================
# ATR MULTIPLIERS
# =============================================================================

ATR_PERIOD       = 14
ATR_PERIOD_DAILY = 14
ATR_PERIOD_SWING = 14

ATR_SL_MULT  = 1.3
ATR_TP_MULT  = 2.4

ATR_SL_DAILY = 6.0
ATR_TP_DAILY = 12.0

ATR_SL_SWING = 2.5
ATR_TP_SWING = 5.0

ATR_SL_SMC   = 1.2
ATR_TP_SMC   = 2.5

ATR_SL_MICRO = 1.0
ATR_TP_MICRO = 2.0

ATR_TRAIL_MULT = 1.0
MIN_TRAIL      = 5.0

# =============================================================================
# TP / SL CAP CONFIG (safety caps applied at order-build time)
# TP_ATR_CAP_MULT: cap TP relative to ATR (tp <= atr * TP_ATR_CAP_MULT)
# TP_SL_MULT: ensure TP is at least this multiple of SL (tp >= sl * TP_SL_MULT)
# These are tunable per-deployment and per-strategy via per-strategy ATR_TP_* values.
# =============================================================================
TP_ATR_CAP_MULT = 6.0
TP_SL_MULT = 3.0

# Per-strategy TP cap multipliers (override global defaults)
# Lower multipliers = tighter TP targets (useful for small TF/scalp strategies)
TP_CAP_SCALP = 3.0      # SCALP targets faster exits (smaller TF)
TP_CAP_SWING = 6.0      # SWING allows bigger moves
TP_CAP_DAILY = 6.5      # DAILY slightly more aggressive
TP_CAP_SMC = 5.5        # SMC balanced
TP_CAP_MICRO = 2.5      # MICRO ultra-tight (smallest TF)

# Per-strategy SL multiplier (ensure TP >= SL * this value)
TP_SL_MULT_SCALP = 2.5  # tighter RR on scalp (1:2.5)
TP_SL_MULT_SWING = 3.0  # standard 1:3 on swing
TP_SL_MULT_DAILY = 3.5  # 1:3.5 on daily
TP_SL_MULT_SMC = 3.0    # standard 1:3
TP_SL_MULT_MICRO = 2.0  # very tight on micro (1:2)

# Per-strategy overrides (fall back to TP_ATR_CAP_MULT / TP_SL_MULT)
TP_ATR_CAP_MULT_PER_STRAT = {
    'SCALP': 2.0,
    'MICRO': 2.0,
    'SWING': 5.0,
    'SMC': 6.0,
}

# [FER3ON-FIX-2026-08-19] رفع TP_SL_MULT ليطابق MULTI_TP_PROFILE الجديد
TP_SL_MULT_PER_STRAT = {
    'SCALP': 2.2,   # كان 2.0
    'MICRO': 2.4,   # كان 2.0 — TP على الأقل 2.4x SL
    'SWING': 3.0,
    'SMC': 3.2,     # كان 3.0
}

# =============================================================================
# BREAK-EVEN (2 STAGES)
# =============================================================================

BREAK_EVEN_ENABLED = True
BREAK_EVEN_R1      = 1.0
BREAK_EVEN_BUFFER  = 0.5
TRAILING_R2        = 2.0

# =============================================================================
# TRADE QUALITY SCORE / GATE — مُفتّح للـ testing mode
# =============================================================================

MIN_QUALITY_SCORE         = 50
QUALITY_SOFT_FLOOR        = 45
QUALITY_CONFIDENCE_BYPASS = 75
QUALITY_SESSION_FLOORS = {
    'ASIA':     55,
    'LONDON':   50,
    'NEW_YORK': 52,
    'OVERLAP':  47,
}
QUALITY_ADAPTIVE_MIN_FLOOR = 42
QUALITY_FLOOR_SMC_ADJ      = -2
QUALITY_FLOOR_CANDLE_ADJ   = -1
QUALITY_FLOOR_SWEEP_ADJ    = -2
QUALITY_FLOOR_MISSED_ADJ   = -2
MIN_RR_RATIO               = 2.0

QUALITY_RISK_TABLE = [
    (95, 0.75),
    (90, 0.60),
    (80, 0.45),
    (70, 0.30),
    (60, 0.20),
    (50, 0.15),
    (45, 0.12),
    (40, 0.10),
    (35, 0.08),
]

# =============================================================================
# CONTEXT MEMORY
# =============================================================================

CONTEXT_MIN_TRADES = 3
CONTEXT_GOOD_WR    = 0.70
CONTEXT_OK_WR      = 0.55
CONTEXT_BAD_WR     = 0.40
CONTEXT_POOR_WR    = 0.30

# =============================================================================
# ENTRY FILTERS — مُفتّح
# =============================================================================

MIN_SCORE_SCALP     = 5
MIN_SCORE_DAILY     = 4

MTF_REQUIRED        = False
DAILY_BIAS_REQUIRED = False
# V3.6: تم تعطيل الحظر الكامل (HARD_GATE) لتعارض الـ Bias/MTF نهائيًا — لا توجد
# استراتيجية تُحظر بالكامل بسبب تعارض اتجاه فقط. القرار الموحّد: التعارض يُخفّض
# اللوت/الوزن/الثقة عبر MTF_CONFLICT_* (V3.6 block أدناه في هذا الملف) ويُمرَّر
# كـ soft penalty في core/unified_decision.py، لكنه لا يمنع الصفقة أبدًا.
# (كانت قديمًا: MTF_HARD_FOR = ('DAILY', 'SWING') / BIAS_HARD_FOR = ('DAILY', 'SWING'))
MTF_HARD_FOR        = ()
BIAS_HARD_FOR       = ('SMC',)
# الاستراتيجيات التي تتلقى عقوبة تعارض أكبر نسبيًا (DAILY/SWING أعلى وزنًا استراتيجيًا
# من SCALP/MICRO، فتعارضها مع الفريم الأعلى أكثر دلالة ويستحق حذرًا أكبر — لا حظرًا)
BIAS_ELEVATED_PENALTY_FOR = ('DAILY', 'SWING')

SMC_MIN_SCORE       = 3.0
SMC_ENTRY_REQUIRED  = True

# =============================================================================
# MARKET REGIME MULTIPLIERS
# =============================================================================

VOLATILE_MULT = 1.5
CRISIS_MULT   = 2.0

# =============================================================================
# SESSION TIMES (UTC)
# =============================================================================

LONDON_START = 7
LONDON_END   = 12
NY_START     = 13
NY_END       = 17

# =============================================================================
# FER3ON FINAL — LONDON OPEN VOLATILE WINDOW (Hard Entry Block)
# Ported from V3.7 (core/settings.py:274-276) per build spec Merge item #2 —
# V3.7 documented 33% WR / -$178 on 36 trades during 08:00-10:00 UTC London
# open. Blocks ALL strategies during this window before any other snapshot
# work runs (see main.py:_build_live_snapshot — FER3ON_FINAL_CHANGELOG.md
# item [MAIN-1]).
# =============================================================================
LONDON_VOLATILE_BLOCK_ENABLED = True
LONDON_VOLATILE_START = 8   # 08:00 UTC (inclusive)
LONDON_VOLATILE_END   = 9   # 09:00 UTC (exclusive) — practical compromise: still hard-blocks the worst of London, but avoids the full 10:00 suppression window.

# =============================================================================
# KILL-SWITCH CONFIGURATION (Strategy Kill-Switch Policy) [FER3ON-2026-08-31]
# Single source of truth for all kill-switch thresholds and behavior.
# All values must be read directly here by core/strategy_kill_switch.py.
# =============================================================================

# Session-level block toggle (disabled as of 2026-08-20 by user request)
# Set to True to block ASIA + NEWYORK sessions for SMC/MICRO strategies
KILL_SWITCH_SESSION_BLOCK_ENABLED = False
KILL_SWITCH_BLOCKED_SESSIONS = {
    "SMC":   {"ASIA", "NEWYORK"},
    "MICRO": {"ASIA", "NEWYORK"},
    "SCALP": set(),
    "DAILY": set(),
}

# Market regime block (enabled)
KILL_SWITCH_REGIME_BLOCK_ENABLED = True
KILL_SWITCH_BLOCKED_REGIMES = {
    "SMC":   {"RANGING"},
    "MICRO": {"RANGING", "TRENDING"},
    "SCALP": set(),
    "DAILY": set(),
}

# Daily loss limits by strategy
KILL_SWITCH_DAILY_LOSS_LIMITS = {
    "SMC":   50.0,
    "MICRO": 30.0,
    "SCALP": 40.0,
    "DAILY": 80.0,
}

# Weekly loss limits by strategy
KILL_SWITCH_WEEKLY_LOSS_LIMITS = {
    "SMC":   120.0,
    "MICRO": 80.0,
    "SCALP": 100.0,
    "DAILY": 200.0,
}

# Consecutive wins required to resume a blocked strategy
KILL_SWITCH_RESUME_AFTER_WINS = 2

# Grace period: minimum trades in current account before kill-switch engages
KILL_SWITCH_MIN_TRADES_FOR_DAILY_BLOCK = 3
KILL_SWITCH_MIN_TRADES_FOR_WEEKLY_BLOCK = 5

# Grace period toggle (allow new accounts to build real sample before blocks)
KILL_SWITCH_GRACE_ENABLED = True
KILL_SWITCH_MIN_TRADES_BEFORE_BLOCK = 8

# Execution grade requirements (strict grades for risky strategies)
KILL_SWITCH_STRICT_EXEC_GRADE_STRATEGIES = {"SMC", "MICRO"}
KILL_SWITCH_ALLOWED_EXEC_GRADES = {"A", "A+", "ELITE"}

# =============================================================================
# FER3ON FINAL — NEWYORK SESSION QUALITY FLOOR
# Ported into core/quality_score.py (build spec Merge item #3). Uses
# V9FINAL1's threshold of 75, NOT V3.7's 80 (too strict) and NOT V9fixed's
# unlimited floor (too permissive) — see FER3ON_FINAL_CHANGELOG.md item
# [QUALITY-1].
# =============================================================================
NEWYORK_MIN_QUALITY_ENABLED = True
NEWYORK_MIN_QUALITY = 75

# =============================================================================
# TIMING — سريع جداً
# =============================================================================

CHECK_INTERVAL     = 60    # إيقاع أكثر استقراراً
TRADE_COOLDOWN     = 200   # V3.5 Phase-1: كان 90 — ضعف الوقت (real enforcement, see main.py)
TRADE_MIN_INTERVAL = 90

# =============================================================================
# V3.5 PHASE-1 — SESSION HARD FILTER
# توثيق تاريخي (قديم): جلسة ASIA سجّلت 22% WR على 86 صفقة — توقّف صارم حتى يثبت العكس.
# تحديث 2026-07-23: هذا التوثيق كان يناقض القيمة الفعلية أدناه (True) منذ فترة.
# البيانات الأحدث (trades.csv، 423 صفقة مغلقة، مؤرشفة في data/history/archive/)
# تُظهر ASIA فعليًا كأفضل جلسة: WR 56.6% على 129 صفقة، وهي الجلسة الوحيدة
# بصافي ربح موجب (+188.60$) — مقابل LONDON/NEWYORK/OFF_HOURS السلبية جميعًا.
# الإبقاء على True هنا مدعوم بالبيانات الفعلية، وليس مجرد عدم تحديث. راجع
# الرقم مرة أخرى بعد تجميع عينة نظيفة جديدة (post sync-fix) قبل أي قرار نهائي.
# =============================================================================
ASIA_TRADING_ENABLED      = True
ASIA_MIN_QUALITY_OVERRIDE = 95      # إذا احتجت تشديدها يدوياً لاحقاً، جودة استثنائية فقط
OFF_HOURS_MAX_TRADES      = 15       # FER3ON FINAL: was 20 — capped at 15 per build spec (V9FINAL1 value)

# =============================================================================
# V3.5 PHASE-2 — OPPORTUNITY QUALITY TIERS
# تصنيف الفرص بدل قبول/رفض ثنائي — يسمح بكثافة ذكية لا عشوائية
# =============================================================================
TIER_GOLD_MIN_SCORE    = 75   # FULL ENTRY — أعلى حجم
TIER_SILVER_MIN_SCORE  = 60   # REDUCED ENTRY — حجم متوسط
TIER_BRONZE_MIN_SCORE  = 48   # MICRO ENTRY — حجم صغير جداً
TIER_REJECT_BELOW      = 48   # رفض كامل

DAILY_GOLD_CAP   = 15   # صفقة ذهبية/يوم
DAILY_SILVER_CAP = 20   # صفقة فضية/يوم
DAILY_BRONZE_CAP = 10   # صفقة برونزية/يوم (micro فقط)
DAILY_TOTAL_CAP  = 40   # سقف يومي كلي عبر جميع الطبقات

# =============================================================================
# V3.5 PHASE-2 — SCALP / SWING STRATEGY PROFILES
# =============================================================================
SCALP_SESSIONS        = ('LONDON', 'NEWYORK', 'OVERLAP')
SCALP_MAX_PER_SESSION  = 8
SCALP_MIN_QUALITY      = 55
SCALP_TP_ATR_MULT      = 1.5
SCALP_SL_ATR_MULT      = 0.8
SCALP_COOLDOWN_SEC      = 120

SWING_MAX_PER_DAY        = 3
SWING_MIN_QUALITY        = 70
SWING_TP_ATR_MULT        = 4.0
SWING_SL_ATR_MULT        = 1.5
SWING_REQUIRE_DAILY_BIAS = True



LOGS_DIR      = 'data/logs'
ANALYTICS_DIR = 'data/analytics'
MEMORY_DIR    = 'data/memory'
HISTORY_DIR   = 'data/history'
BACKUP_DIR    = 'data/backups'

import os
ALLOW_LIVE_TRADING = os.getenv('ALLOW_LIVE_TRADING', 'False').lower() in ('true', '1', 'yes')

# =============================================================================
# SELF OPTIMIZER + ADAPTIVE LEARNING
# =============================================================================

OPTIMIZER_CYCLE   = 30
OPTIMIZER_ENABLED = True

ADAPTIVE_LEARNING_ENABLED   = True
ADAPTIVE_MIN_TRADES_TO_TUNE = 8
ADAPTIVE_TUNE_INTERVAL      = 15
ADAPTIVE_THRESHOLD_STEP     = 0.5
ADAPTIVE_MAX_TIGHTEN        = 5
ADAPTIVE_MAX_RELAX          = 10
ADAPTIVE_WR_GOOD_LIFT       = 0.60
ADAPTIVE_WR_BAD_TIGHTEN     = 0.40

# =============================================================================
# ANTI-REVENGE SYSTEM
# =============================================================================

ANTI_REVENGE_ENABLED      = True
ANTI_REVENGE_LOSS_TRIGGER = 4
ANTI_REVENGE_RISK_MULT    = 0.50

# =============================================================================
# DAILY REPORT
# =============================================================================

DAILY_REPORT_HOUR = 21

# =============================================================================
# CHOCH ENGINE
# =============================================================================

CHOCH_ENABLED      = True
CHOCH_MIN_STRENGTH = 'WEAK'

# =============================================================================
# LIQUIDITY MAP
# =============================================================================

LIQ_MAP_ENABLED   = True
LIQ_MAP_MIN_SCORE = 3

# =============================================================================
# ADAPTIVE WEIGHTING
# =============================================================================

ADAPTIVE_WEIGHTS_ENABLED = True
ADAPTIVE_CYCLE_SIZE      = 50

# =============================================================================
# EXECUTION INTELLIGENCE
# =============================================================================

EXEC_INTEL_ENABLED   = True
EXEC_INTEL_MIN_GRADE = 'C'
EXEC_INTEL_HARD_BLOCK_ONLY_CATASTROPHIC = True

# =============================================================================
# SURVIVAL INTELLIGENCE
# =============================================================================

SURVIVAL_MODE_ENABLED = True

# =============================================================================
# V7 — EXECUTION INTELLIGENCE
# =============================================================================

V7_ENABLED = True

V7_MISSED_OPPORTUNITY_ENABLED = True
V7_MISSED_EVAL_MINUTES        = 15
V7_MOVEMENT_THRESHOLDS        = [5, 10, 15, 20]

V7_OPPORTUNITY_ENGINE_ENABLED = True
V7_OPPORTUNITY_MIN_CONFIDENCE = 50   # V3.5 softened (was 40)
V7_OPPORTUNITY_QUARTER_MAX    = 69   # V3.5 widened (was 75)
V7_OPPORTUNITY_HALF_MAX       = 79   # V3.5 widened (was 85)

V7_DYNAMIC_THRESHOLD_ENABLED = True
V7_THRESHOLD_ASIA            = 58
V7_THRESHOLD_LONDON          = 52
V7_THRESHOLD_NEWYORK         = 55
V7_THRESHOLD_OVERLAP         = 50
V7_THRESHOLD_VOLATILE_ADJ    = 5
V7_THRESHOLD_CRISIS_ADJ      = 10

V7_SCALE_IN_ENABLED = True

V7_VELOCITY_ENABLED       = True
V7_VELOCITY_MAX_BONUS     = 8

# V9-prep: تم ربط core/v7_integration.py + velocity_engine.py فعليًا بـ
# core/trade_executor.py (كان معزولاً عن main.py تمامًا قبل ذلك). سقف ضيق
# جدًا ومتعمَّد — "جريء لكن غير متهور": بونص الزخم يكبّر اللوت بحد أقصى 8%
# (V7_VELOCITY_MAX_BONUS=8 نقطة ثقة → 8/100=0.08 → لكن نحدّها هنا بسقف
# منفصل وأكثر تحفظًا تحسبًا لأي تغيير مستقبلي في V7_VELOCITY_MAX_BONUS).
V7_MAX_LOT_BOOST          = 0.08

V7_MICRO_TRIGGER_ENABLED  = True
V7_MICRO_TRIGGER_REQUIRED = False

V7_CONFIDENCE_DECAY_ENABLED = True

V7_LIQUIDITY_VACUUM_ENABLED = True
V7_VACUUM_FAST_EXEC_SCORE   = 60

V7_SWEEP_PREDICTOR_ENABLED  = True
V7_SWEEP_MAX_BONUS          = 6

V7_FINAL_BRAIN_WAIT_FLOOR   = 45
V7_FINAL_BRAIN_REJECT_FLOOR = 40
V7_FINAL_BRAIN_FULL_FLOOR   = 68
V7_FINAL_BRAIN_REDUCED_FLOOR= 48
V7_VACUUM_EXEC_BONUS        = 5

V7_CANDLE_CONTEXT_ENABLED   = True
V7_CANDLE_CONTEXT_MAX_BONUS = 5

# =============================================================================
# UNIFIED DECISION
# =============================================================================

UNIFIED_DECISION_ENABLED = True
UNIFIED_DECISION_PRIMARY = True
UNIFIED_DECISION_MODES   = ('HARD_BLOCK', 'PASS_FULL', 'PASS_REDUCED', 'PASS_MICRO')

# مُفتّح للـ testing mode
COMPOSITE_FULL_MIN      = 70
COMPOSITE_REDUCED_MIN   = 50
COMPOSITE_MICRO_MIN     = 50

UNIFIED_WAIT_ALLOWED_ONLY_FOR = ('MARKET_CLOSED', 'TIMING_WINDOW')

COMPOSITE_WEIGHTS = {
    'quality':    0.30,
    'confidence': 0.25,
    'brain':      0.20,
    'execution':  0.15,
    'context':    0.10,
}

# =============================================================================
# V3 — SMC SIGNAL-LAYER WEIGHTS
# =============================================================================

SMC_V3_WEIGHT       = 0.07
SMC_V3_BONUS_CAP    = 7.0
SMC_V3_BONUS_FLOOR  = -2.0

# =============================================================================
# V6 RECOVERY+
# =============================================================================

V7_PLUS_ENABLED = True

V7_SMC_ARBITRATION_ENABLED   = True
V7_SMC_ARBITRATION_MAX_BONUS = 8
V7_SMC_ARBITRATION_MIN_SCORE = 4.0
V7_SMC_ARBITRATION_RATIO     = 1.6

V7_FILTER_RELAXATION_ENABLED = True
V7_FILTER_RELAXATION_MAX     = 0.30

V7_HARD_RISK_CAP_ENABLED        = True
HARD_RISK_MAX_PER_TRADE         = 0.50
HARD_RISK_MAX_PER_TRADE_CEILING = 1.00
HARD_RISK_DAILY_LOSS_PERCENT    = 5.0  # must match MAX_RISK_PER_DAY_PERCENT

V7_SESSION_INTELLIGENCE_ENABLED = True

V7_RECOVERY_DASHBOARD_ENABLED = True
V7_DASHBOARD_UPDATE_INTERVAL  = 120

V7_RECOVERY_MAX_TOTAL_BONUS   = 15

# =============================================================================
# ML CONFIG
# =============================================================================

ML_HARD_REJECT_THRESHOLD = 0.28
ML_RL_SKIP_THRESHOLD     = 0.45
ML_AS_MODIFIER           = True
ML_VETO_REQUIRES_LOW_QUALITY = True

# =============================================================================
# OPTIMIZER
# =============================================================================

OPTIMIZER_PRESSURE_BLOCK = 15
OPTIMIZER_AS_TUNER       = True
OPTIMIZER_AS_BLOCKER     = False

# =============================================================================
# AI V1 — LAYERED RISK SHAPING
# =============================================================================

AI_V1_RISK_MULT_FULL       = 1.00
AI_V1_RISK_MULT_PREMIUM    = 1.30
AI_V1_RISK_MULT_REDUCED    = 0.75
AI_V1_RISK_MULT_MICRO      = 0.50
AI_V1_RISK_MULT_CRISIS_MICRO = 0.40

AI_V1_MICRO_MAX_PER_SESSION   = 25
AI_V1_MICRO_MAX_CONSECUTIVE   = 6
AI_V1_MICRO_MIN_SPACING_SEC   = 60

# =============================================================================
# V2.2 TESTING MODE — مُفتّح لـ 80 صفقة يومياً
# =============================================================================
TESTING_MODE = False
ML_FEATURE_COUNT = 22

# --- تغيير جذري: 80 صفقة يومياً بدل 8 ---
# FER3ON FINAL: reduced from 100 to 50 per build spec Action Plan #6
# (recommended range 40-60; this is also the single source of truth now —
# core/trade_executor.py's live daily counter imports this value instead of
# its own separate hardcoded 100, see FER3ON_FINAL_CHANGELOG.md [EXEC-1]).
MAX_DAILY_TRADES = 50
MAX_SCALP_TRADES_PER_DAY = 30
MAX_MICRO_TRADES_PER_DAY = 40
MAX_SMC_TRADES_PER_DAY = 30
MAX_DAILY_SWING_TRADES_PER_DAY = 15

# --- Lot caps للـ 1000$ ---
TESTING_MODE_LOT_CAPS = {
    'MICRO': 0.02,   # بقرار المستخدم: كان 0.01
    'REDUCED': 0.15,
    'FULL': 0.15,
}

TESTING_MODE_RISK_MULTIPLIERS = {
    'MICRO': 0.50,
    'REDUCED': 0.75,
    'NORMAL': 1.00,
}

# --- thresholds مُفتّحة ---
TESTING_MODE_QUALITY_THRESHOLDS = {
    'FULL': 60,
    'REDUCED': 45,
    'MICRO': 35,
    'BLOCK': 30,
}

COUNTER_TREND_SCALP_ENABLED = True
COUNTER_TREND_SCALP_MIN_RISK = 0.05
COUNTER_TREND_SCALP_MAX_RISK = 0.15
COUNTER_TREND_SCALP_TP_ATR = 2.5
COUNTER_TREND_SCALP_SL_ATR = 1.5
COUNTER_TREND_SCALP_SIGNALS = (
    'CHOCH',
    'LIQUIDITY_SWEEP',
    'MOMENTUM_BREAKOUT',
    'STRONG_REJECTION',
    'FAST_REVERSAL',
    'MARKET_STRUCTURE_SHIFT',
)

MICRO_ENGINE_RISK = 0.01
MICRO_ENGINE_TP_ATR = 4.0
MICRO_ENGINE_SL_ATR = 2.0
MICRO_ENGINE_MAX_PER_SESSION = 30

SMC_COUNTERTREND_OPPORTUNITY_SCORE = 80
SMC_COUNTERTREND_RISK_REDUCTION = 0.50

PRODUCTION_LOG_CLEAN_MODE = True

# =============================================================================
# AI V1 — DECISION TELEMETRY
# =============================================================================
AI_V1_LOG_DECISIONS    = True
AI_V1_LOG_EVIDENCE     = True
AI_V1_SHOW_BRAND_BANNER = True

# =============================================================================
# TELEGRAM COMMANDS REFERENCE
# =============================================================================
# /start      — تشغيل البوت
# /stop       — إيقاف البوت
# /stats      — إحصاءات كاملة
# /report     — تقرير يومي
# /quality    — إعدادات جودة الصفقة
# /context    — ذاكرة السياق
# /optimize   — تشغيل Self-Optimizer يدوياً
# /choch      — تحليل CHOCH الحالي
# /liqmap     — خريطة السيولة
# /weights    — الأوزان التكيفية الحالية
# /adapt      — تشغيل Adaptive Weighting يدوياً
# /retrain    — إعادة تدريب ML يدوياً
# /mlstats    — إحصاءات نماذج ML
# /liquidity  — Liquidity Intelligence
# /structure  — Market Structure
# /tune       — حالة Adaptive Learning

# =============================================================================
# FER3ON V3.5 — PHASE-1 MICRO SOFT STABILIZATION (+10% strictness)
# زيادة التشدد بنسبة 10% (تهدئة وليس خنق)
#   Confidence 30 → 35
#   Confidence 35 → 40
#   Score      55 → 60
#   Score      60 → 65
# =============================================================================
# عتبات MICRO الجديدة (تطبيق فقط إن لم تكن مفعّلة يدوياً)
MICRO_CONFIDENCE_THRESHOLD_OLD_30 = 35   # كان 30
MICRO_CONFIDENCE_THRESHOLD_OLD_35 = 40   # كان 35
MICRO_SCORE_THRESHOLD_OLD_55      = 60   # كان 55
MICRO_SCORE_THRESHOLD_OLD_60      = 65   # كان 60

# قائمة موحّدة لطبقة المايكرو
# V3.7 (2026-07): رُفعت من 40 -> 45 بناءً على بيانات فعلية (trades.csv /
# mt5_trade_history.csv قبل الأرشفة): MICRO كانت الاستراتيجية الأضعف أداءً
# بفارق واضح عن SMC (win rate ~32-42% وصافي ربح سلبي بوضوح)، وهي استمرار
# لنفس منطق التشديد التدريجي لـ V3.5 Phase-1 (35 -> 40) أعلاه، وليس تراجعًا
# عنه. راجع النتيجة الفعلية بعد تجميع عينة صفقات نظيفة جديدة قبل أي رفع إضافي.
#
# بقرار المستخدم: جولة تشديد إضافية +10% فوق قيم V3.7 (مايكرو فقط، باقي
# الاستراتيجيات لم تُمس).
MICRO_CONFIDENCE_THRESHOLD_OLD_45 = 50   # كان 45 (+10%)
MICRO_SCORE_THRESHOLD_OLD_60_V2   = 66   # كان 60 (+10%)

MICRO_MIN_CONFIDENCE_DEFAULT      = MICRO_CONFIDENCE_THRESHOLD_OLD_45   # 50
MICRO_MIN_SCORE_DEFAULT           = MICRO_SCORE_THRESHOLD_OLD_60_V2     # 66
MICRO_STABILIZATION_ACTIVE        = True   # مفتاح التفعيل
MICRO_STRATEGY_ENABLED            = True  # سياسة التشغيل: MICRO مُوقّف مؤقتًا

# FER3ON MICRO — EMA directional bonus (NON-VETO)
# لا يرفض الصفقة، بل يضيف نقاط جودة فقط عند توافق الاتجاه مع EMA.
MICRO_EMA_DIRECTION_BONUS_ENABLED = True
MICRO_EMA_DIRECTION_BONUS_POINTS = 2
MICRO_EMA_DIRECTION_VETO_ENABLED = False

# بقرار المستخدم: أقصى حجم لوت مسموح به لصفقات MICRO تحديدًا (بغض النظر عن
# أي حساب مخاطرة/رصيد أعلى) — راجع core/risk_manager.py::calculate_smart_lot
# حيث يُطبَّق هذا كسقف نهائي بعد كل حسابات اللوت الأخرى. نفس الإعداد اللي
# طُبِّق على نسخة STRICT10 قبل كده.
MICRO_MAX_LOT = 0.02

# =============================================================================
# FER3ON V3.5 — CANDLE CONFIRMATION (Phase-1)
# عدم اعتماد أنماط على شمعة واحدة فقط.
# REJECTION / INSIDE BAR / MOMENTUM BREAKOUT → تظهر فقط بعد شمعتين متتاليتين
# بنفس الاتجاه أو شمعة تأكيد إضافية.
# =============================================================================
CANDLE_CONFIRMATION_ENABLED         = True
CANDLE_CONFIRMATION_REQUIRE_2_BARS  = True   # REJECTION / INSIDE BAR / MOMENTUM-BREAKOUT
CANDLE_CONFIRMATION_ALLOW_CONT_TREND = False  # إذا الثانية معاكسة = لا إشارة

# =============================================================================
# FER3ON V3.5 — ML RUNTIME DOWNGRADE (Phase-1)
# طالما ML != REAL، الـ ML:
#   * لا يحجب / لا يرفض / لا يلغي أي صفقة
#   * يعمل فقط كـ ADVISOR بحد أقصى ±5 نقاط على Composite
# =============================================================================
ML_AUTHORITY_WEIGHT = 0.00   # لا veto
ML_ADVISOR_WEIGHT   = 0.15
ML_BOOST_MAX_POINTS = +5
ML_PENALTY_MAX_PTS  = -5
ML_BLOCK_ALLOWED    = False
ML_REJECT_ALLOWED   = False
ML_OVERRIDE_ALLOWED = False

# =============================================================================
# FER3ON V3.5 — PORTFOLIO RISK AUTHORITY (Phase-1)
# Authority هو "Portfolio Risk Authority" فقط:
#   - يدير المخاطر (Risk Control)
#   - يخصص اللوت (Lot Allocation)
#   - يدير الانكشاف (Exposure Management)
#   - يطبق حدود المحفظة (Portfolio Limits)
#   - حماية الخسارة اليومية (Daily Loss Protection)
#   - حماية الاستنزاف (Drawdown Protection)
# ممنوع على Authority رفض صفقة بسبب اختلاف استراتيجية أخرى.
# الاختلاف بين استراتيجيات = Portfolio Diversification لا Conflict.
# =============================================================================
PORTFOLIO_RISK_AUTHORITY_ACTIVE     = True
PORTFOLIO_RISK_AUTHORITY_CAN_REJECT = (
    "EMERGENCY_STOP",
    "DAILY_LOSS_LIMIT_HIT",
    "MAX_DRAWDOWN_HIT",
    "LOT_CAP_HIT",
    "EXPOSURE_LIMIT_HIT",
    "RISK_LIMITS_HIT",
)
PORTFOLIO_RISK_AUTHORITY_CANNOT_REJECT_FOR = (
    "STRATEGY_CONFLICT",
    "CROSS_STRATEGY_DIRECTION_MISMATCH",
    "BIAS_VS_STRATEGY_MISMATCH",
)

# =============================================================================
# FER3ON V3.5 — TRUTH LAYER
# مسار تخزين تقارير الحقيقة الموحدة
# =============================================================================
TRUTH_LAYER_DIR = 'data/truth_layer'
TRUTH_LAYER_TRADE_HISTORY = 'data/truth_layer/trade_history.json'
TRUTH_LAYER_DAILY_REPORT = 'data/truth_layer/daily_reports.json'
TRUTH_LAYER_STRATEGY_BREAKDOWN = 'data/truth_layer/strategy_breakdown.json'
TRUTH_LAYER_SESSION_BREAKDOWN = 'data/truth_layer/session_breakdown.json'
TRUTH_LAYER_REGIME_BREAKDOWN = 'data/truth_layer/regime_breakdown.json'
SMC_DEBUG_REPORT_DIR = 'data/truth_layer/smc_diagnostics'
# =============================================================================
# FER3ON V3+++ — PHASE 2 PERFORMANCE INTELLIGENCE
# Analytics-only sidecar. Zero runtime influence.
# =============================================================================

PHASE2_ANALYTICS_DIR         = "data/analytics/phase2"
PHASE2_REPORTS_DIR           = "data/analytics/phase2/reports"
PHASE2_RANKINGS_DIR          = "data/analytics/phase2/rankings"
PHASE2_CONTRIB_DIR           = "data/analytics/phase2/contributions"
PHASE2_SHADOW_DIR            = "data/analytics/phase2/shadow"

PHASE2_ENABLED                    = True
PHASE2_RUNTIME_INFLUENCE          = False   # NEVER flip to True in this phase
PHASE2_SHADOW_CALIBRATION_ONLY    = True
PHASE2_MIN_SAMPLE_PER_BUCKET      = 5       # below this → INSUFFICIENT_SAMPLE

# =============================================================================
# FER3ON — PHASE 3 INSTITUTIONAL SHADOW ARCHITECTURE
# =============================================================================
# كل مكوّنات Phase 3 تعمل في وضع Shadow فقط حتى تحقيق شروط التفعيل.
# Settings هو المصدر الوحيد للحقيقة — لا hardcoded thresholds.
# كل التغييرات قابلة للعكس بالكامل من هنا.
# =============================================================================

# --- Phase 3 Directory Paths ---
PHASE3_ANALYTICS_DIR        = "data/analytics/phase3"
PHASE3_FINAL_BRAIN_DIR      = "data/analytics/phase3/final_brain"
PHASE3_PORTFOLIO_BRAIN_DIR  = "data/analytics/phase3/portfolio_brain"
PHASE3_GOLD_CONTEXT_DIR     = "data/analytics/phase3/gold_context"
PHASE3_ML_SAFETY_DIR        = "data/analytics/phase3/ml_safety"
PHASE3_STRATEGY_DNA_DIR     = "data/analytics/phase3/strategy_dna"
PHASE3_SYSTEM_HEALTH_DIR    = "data/analytics/phase3/system_health"
PHASE3_SHADOW_LOG_DIR       = "data/analytics/phase3/shadow_log"

# --- Phase 3 Global Switch ---
# لا تُفعّل هذا إلا بعد اجتياز جميع شروط التفعيل
PHASE3_ENABLED              = True   # تفعيل البنية (Shadow فقط)
PHASE3_LIVE_AUTHORITY       = False  # سلطة حية — ممنوع قبل اكتمال الشروط

# --- Activation Requirements (conditions to promote Shadow → Live) ---
PHASE3_REQUIRED_CLOSED_TRADES    = 500    # حد أدنى من الصفقات المغلقة
PHASE3_REQUIRED_WIN_RATE_MIN     = 0.45   # حد أدنى لـ WR قبل التفعيل
PHASE3_REQUIRED_SHADOW_CYCLES    = 200    # دورات shadow كاملة مطلوبة
PHASE3_REQUIRED_FALSE_REJECT_MAX = 0.10   # أقصى نسبة رفض خاطئ مسموح بها

# =============================================================================
# FINAL_BRAIN — Shadow Approval Authority
# =============================================================================
FINAL_BRAIN_ENABLED          = True   # تفعيل المكوّن (Shadow دائماً أولاً)
FINAL_BRAIN_LIVE_AUTHORITY   = False  # لا سلطة حية حتى تكتمل الشروط
FINAL_BRAIN_SHADOW_LOG       = True   # تسجيل كل قرار shadow
FINAL_BRAIN_MIN_APPROVAL_SCORE    = 60.0  # حد أدنى للموافقة
FINAL_BRAIN_MIN_REJECT_SCORE      = 40.0  # حد أقصى للرفض (أقل من هذا = رفض)
FINAL_BRAIN_RANKING_ENABLED       = True  # تفعيل ترتيب الإعدادات
FINAL_BRAIN_MAX_SETUPS_PER_CYCLE  = 3     # أقصى عدد إعدادات يوافق عليها في الدورة

# =============================================================================
# PORTFOLIO_BRAIN — Institutional Capital Intelligence
# =============================================================================
PORTFOLIO_BRAIN_ENABLED         = True
PORTFOLIO_BRAIN_LIVE_AUTHORITY  = False
PORTFOLIO_BRAIN_SHADOW_LOG      = True
# أوزان التخصيص لكل استراتيجية (يمكن تعديلها من هنا)
PORTFOLIO_BRAIN_STRATEGY_WEIGHTS = {
    "SCALP": 0.30,
    "SMC":   0.30,
    "SWING": 0.20,
    "DAILY": 0.15,
    "MICRO": 0.05,
}
PORTFOLIO_BRAIN_MAX_EXPOSURE_PCT      = 0.60   # أقصى انكشاف إجمالي 60%
PORTFOLIO_BRAIN_DIVERSITY_TARGET      = 3      # استهداف 3+ استراتيجيات نشطة
PORTFOLIO_BRAIN_CAPITAL_PRESSURE_WARN = 0.80   # تحذير عند 80% استخدام رأس المال

# =============================================================================
# GOLD_CONTEXT_LAYER — XAUUSD Macro Intelligence
# =============================================================================
GOLD_CONTEXT_ENABLED         = True
GOLD_CONTEXT_LIVE_INFLUENCE  = False   # modifier فقط — لا يحجب وحده
GOLD_CONTEXT_SHADOW_LOG      = True
# أوزان عوامل السياق الماكرو (المجموع يساوي 1.0)
GOLD_CONTEXT_FACTOR_WEIGHTS = {
    "dxy_trend":        0.20,
    "real_yields":      0.20,
    "cpi_pressure":     0.15,
    "nfp_momentum":     0.10,
    "fomc_stance":      0.15,
    "geopolitical":     0.10,
    "rate_differential":0.10,
}
GOLD_CONTEXT_MAX_POSITIVE_INFLUENCE = +8.0   # أقصى تأثير إيجابي على الدرجة
GOLD_CONTEXT_MAX_NEGATIVE_INFLUENCE = -8.0   # أقصى تأثير سلبي على الدرجة
GOLD_CONTEXT_HARD_BLOCK_ALLOWED     = False  # ممنوع الحجب المنفرد

# =============================================================================
# ML_SAFETY_FRAMEWORK — Model Health & Drift Detection
# =============================================================================
ML_SAFETY_ENABLED            = True
ML_SAFETY_LIVE_BLOCK         = False   # لا حجب حي — مراقبة فقط
ML_SAFETY_SHADOW_LOG         = True
ML_SAFETY_DRIFT_THRESHOLD    = 0.15    # عتبة انجراف النموذج (15%)
ML_SAFETY_HEALTH_WARN_BELOW  = 60.0   # تحذير صحة النموذج تحت 60
ML_SAFETY_HEALTH_ALERT_BELOW = 40.0   # إنذار صحة النموذج تحت 40
ML_SAFETY_RECHECK_INTERVAL   = 3600   # فحص دوري كل ساعة (ثانية)
ML_SAFETY_RETRAIN_RECOMMEND_AT = 200  # توصية بإعادة التدريب عند هذا العدد من الصفقات

# =============================================================================
# STRATEGY_DNA — Strategy Performance Intelligence
# =============================================================================
STRATEGY_DNA_ENABLED         = True
STRATEGY_DNA_LIVE_INFLUENCE  = False
STRATEGY_DNA_SHADOW_LOG      = True
STRATEGY_DNA_LOOKBACK_TRADES = 100    # نافذة تقييم الأداء (آخر N صفقة)
STRATEGY_DNA_RANK_INTERVAL   = 50     # إعادة الترتيب كل N صفقة
STRATEGY_DNA_PENALTY_WR_BELOW = 0.35 # عقوبة استراتيجية WR أقل من 35%
STRATEGY_DNA_BONUS_WR_ABOVE   = 0.65 # مكافأة استراتيجية WR فوق 65%

# =============================================================================
# SYSTEM_HEALTH_LAYER — Unified Health Monitor
# =============================================================================
SYSTEM_HEALTH_ENABLED        = True
SYSTEM_HEALTH_SHADOW_LOG     = True
SYSTEM_HEALTH_CHECK_INTERVAL = 300    # فحص كل 5 دقائق (ثانية)
SYSTEM_HEALTH_WARN_SCORE     = 70.0   # تحذير تحت 70
SYSTEM_HEALTH_ALERT_SCORE    = 50.0   # إنذار تحت 50
SYSTEM_HEALTH_CRITICAL_SCORE = 30.0   # حرج تحت 30

# =============================================================================
# ADAPTIVE_LEARNING_SHADOW — Shadow Calibration Only
# =============================================================================
ADAPTIVE_SHADOW_ONLY              = True   # وضع shadow — لا تعديل حي للـ thresholds
ADAPTIVE_SHADOW_LOG               = True
ADAPTIVE_SHADOW_CONFIDENCE_SUGGESTIONS = True  # يوصي بـ confidence thresholds
ADAPTIVE_SHADOW_SESSION_PREF      = True       # يوصي بأفضل الجلسات
ADAPTIVE_SHADOW_STRATEGY_RANKING  = True       # يوصي بترتيب الاستراتيجيات
# ممنوع تغيير هذه الأشياء في Phase 3 الأولى:
ADAPTIVE_SHADOW_CANNOT_CHANGE = (
    "core_trading_logic",
    "direction_logic",
    "execution_logic",
    "default_thresholds_live",
    "entry_conditions",
    "risk_ratios",
)

# =============================================================================
# V3.6 — TREND CONFLUENCE LAYER (Per-Timeframe Trend + Channel + Candles)
# =============================================================================
# الفلسفة:
#   كل استراتيجية تحسب ترندها + قناتها السعرية + شموعها على فريمها الخاص
#   بشكل مستقل تمامًا، ثم تُقارَن النتيجة فقط باتجاه الفريم المرجعي الأعلى.
#   التوافق يرفع اللوت/الثقة. التعارض يخفّضهم. لا حظر كامل أبدًا
#   (advisory bonus/penalty فقط — نفس فلسفة candle_gate_v3.py).
# =============================================================================

TREND_CONFLUENCE_ENABLED = True

# الفريم الأساسي (تُحسب عليه الترند/القناة/الشموع) لكل استراتيجية
TREND_PRIMARY_TF = {
    "MICRO": "M1",
    "SCALP": "M5",
    "SMC":   "H1",
    "DAILY": "H4",
}

# الفريم المرجعي الأعلى (للمقارنة فقط — لا حسابات مشتركة)
TREND_REFERENCE_TF = {
    "MICRO": "H1",
    "SCALP": "H1",
    "SMC":   "H4",
    "DAILY": "W1",
}

# حساسية رسم الترند (lookback لاكتشاف القمم/القيعان المحلية - pivot)
# فريمات سريعة = حساسية مخففة (أقل لمسات لازمة) لتجنب التأخر عن السعر
TREND_PIVOT_LOOKBACK = {
    "M1":  2,
    "M5":  3,
    "M15": 3,
    "H1":  5,
    "H4":  5,
    "D1":  5,
    "W1":  5,
}

# الحد الأدنى لعدد اللمسات لاعتبار خط الترند صالحًا
TREND_MIN_TOUCHES = 3

# نطاق الزاوية المقبول لخط الترند (تطبيع عملي لمقياس XAUUSD)
TREND_MIN_ANGLE_DEG = 15
TREND_MAX_ANGLE_DEG = 75


# =============================================================================
# HELPER FUNCTIONS FOR TP CAPPING
# =============================================================================

def get_tp_cap_multiplier(strategy: str) -> float:
    """Get per-strategy TP ATR cap multiplier."""
    s = (strategy or 'UNKNOWN').upper()
    return {
        'SCALP': TP_CAP_SCALP,
        'SWING': TP_CAP_SWING,
        'DAILY': TP_CAP_DAILY,
        'SMC': TP_CAP_SMC,
        'MICRO': TP_CAP_MICRO,
    }.get(s, TP_ATR_CAP_MULT)  # fallback to global default


def get_tp_sl_multiplier(strategy: str) -> float:
    """Get per-strategy TP/SL ratio multiplier."""
    s = (strategy or 'UNKNOWN').upper()
    return {
        'SCALP': TP_SL_MULT_SCALP,
        'SWING': TP_SL_MULT_SWING,
        'DAILY': TP_SL_MULT_DAILY,
        'SMC': TP_SL_MULT_SMC,
        'MICRO': TP_SL_MULT_MICRO,
    }.get(s, TP_SL_MULT)  # fallback to global default

# أقصى بونص/عقوبة من محاذاة الترند (تُضاف إلى composite_delta — لا تُرفض صفقة بمفردها)
TREND_CONFLUENCE_MAX_BONUS   = 4.0
TREND_CONFLUENCE_MAX_PENALTY = 3.0

# تُطبَّق طبقة الترند الكاملة (bonus إضافي على unified_decision) على DAILY/SMC فقط
# — أما المحاذاة المتعددة الفريمات (MTF alignment sizing) فتُطبَّق على الأربعة جميعًا
TREND_CONFLUENCE_BONUS_FOR = ("DAILY", "SMC")

# =============================================================================
# V3.6 — MULTI-TIMEFRAME ALIGNMENT SIZING (لكل الاستراتيجيات الأربع)
# =============================================================================
# عند توافق اتجاه الفريم الأساسي مع الفريم المرجعي الأعلى → لوت/وزن كامل
# عند التعارض → لوت/وزن مصغّر (حذر) — **لا يُمنع الدخول أبدًا**
# =============================================================================

MTF_ALIGNED_LOT_MULT   = 1.00
MTF_NEUTRAL_LOT_MULT   = 0.75   # أحد الفريمين بلا اتجاه واضح (NONE)
MTF_CONFLICT_LOT_MULT  = 0.35   # تعارض حقيقي بين الفريمين

MTF_ALIGNED_WEIGHT_MULT  = 1.00
MTF_NEUTRAL_WEIGHT_MULT  = 0.85
MTF_CONFLICT_WEIGHT_MULT = 0.50

# عقوبة/بونص نقطي يُضاف إلى composite_delta في unified_decision (بالتوافق مع
# نمط BIAS_CONFLICT / COUNTER_TREND_REVERSAL الموجود مسبقًا في الكود)
MTF_ALIGNED_SCORE_BONUS   = 3.0
MTF_CONFLICT_SCORE_PENALTY = -4.0

# =============================================================================
# V3.6 — CANDLE CONFIRMATION RULES (Per-Timeframe — لا قاعدة واحدة للجميع)
# =============================================================================
# فريمات سريعة (M1/M5): شمعة واحدة كافية (انتظار شمعتين = فوات التوقيت)
# فريمات متوسطة/بطيئة (M15+): شمعتين تأكيد لأنماط الشمعة الواحدة فقط
# (Tier A — Engulfing/3 Soldiers/Crows مستثناة، لأنها متعددة الشموع أصلاً)
# =============================================================================

CANDLE_SINGLE_CONFIRM_TF = ("M1",)                 # شمعة واحدة فقط
CANDLE_BONUS_ON_DOUBLE_TF = ("M5",)                # شمعة واحدة + بونص لو شمعتين متوافقتين
CANDLE_DOUBLE_CONFIRM_TF = ("M15", "H1", "H4", "D1", "W1")  # شمعتين إلزامي (لأنماط Tier B/C)

CANDLE_DOUBLE_CONFIRM_PATTERNS = (
    "PIN_BAR", "PINBAR_BUY", "PINBAR_SELL",
    "HAMMER", "SHOOTING_STAR",
    "REJECTION_BUY", "REJECTION_SELL", "REJECTION",
    "INSIDE_BAR_BREAKOUT", "MOMENTUM_BREAKOUT",
)
CANDLE_DOUBLE_CONFIRM_PARTIAL_BONUS = 0.5  # نسبة البونص المُمنوحة لو التأكيد الثاني غائب (تخفيف لا حظر)
CANDLE_M5_DOUBLE_BONUS_MULT = 1.25         # بونص إضافي 25% لـ M5 لو شمعتين متتاليتين متوافقتين

# =============================================================================
# V3.6 — MULTI-TP LADDER (TP1 / TP2 / TP3) — نِسَب حسب طبيعة كل استراتيجية
# =============================================================================
# كل قيمة % تمثل نسبة إغلاق الحجم عند هذا الهدف. المجموع لكل استراتيجية = 100%
# RR تقريبي إرشادي (تُحسب فعليًا من ATR/structure حسب الاستراتيجية)
# =============================================================================

MULTI_TP_ENABLED = True

MULTI_TP_STRATEGY_ENABLED = {
    "DAILY": True,
    "SMC": True,
    "SCALP": True,
    "MICRO": True,
}

# [FER3ON-FIX-2026-08-19] RR ANTI-REVERSAL PATCH
# البيانات الحقيقية (120 صفقة) أظهرت:
#   SMC   : R:R فعلي = 0.67  → خسارة صافية -249$
#   MICRO : R:R فعلي = 0.93  → خسارة صافية -130$
#   MANUAL: R:R فعلي = 1.24  → ربح صافي   +143$  ← نقلده
# السبب: tp1_rr=1.0 يقفل نصف الصفقة عند 1R، والباقي يضرب SL كامل
# → متوسط الربح < متوسط الخسارة رياضيًا.
# الحل: رفع tp1_rr وتقليل حجم TP1 لإطالة العمر الفعلي للصفقة الرابحة.
MULTI_TP_PROFILE = {
    "DAILY": {"tp1_pct": 0.30, "tp2_pct": 0.35, "tp3_pct": 0.35,
              "tp1_rr": 1.5, "tp2_rr": 2.5, "tp3_rr": 4.0},
    "SMC":   {"tp1_pct": 0.35, "tp2_pct": 0.35, "tp3_pct": 0.30,
              "tp1_rr": 1.5, "tp2_rr": 2.5, "tp3_rr": 4.0},
    "SCALP": {"tp1_pct": 0.45, "tp2_pct": 0.55, "tp3_pct": 0.0,
              "tp1_rr": 1.5, "tp2_rr": 2.5, "tp3_rr": 0.0},
    "MICRO": {"tp1_pct": 0.50, "tp2_pct": 0.50, "tp3_pct": 0.0,
              "tp1_rr": 1.5, "tp2_rr": 2.5, "tp3_rr": 0.0},
}

# عند تعارض MTF (CONFLICT) — يتجاوز الجدول أعلاه: هدف واحد سريع وحذِر فقط
# [FER3ON-FIX-2026-08-19] رفع من 0.8 إلى 1.2 (لا نقبل صفقة R:R سالب حتى في conflict)
MULTI_TP_CONFLICT_MODE = {
    "tp1_pct": 1.00, "tp1_rr": 1.2,
}

# V3.6: حارس RR ديناميكي حسب الاستراتيجية (يستبدل القيمة الثابتة 1.8 الموحّدة
# في trade_executor.py). كل قيمة = هامش أمان أسفل tp1_rr المخطط لها في
# MULTI_TP_PROFILE — يحمي من صفقات RR سيئة بدون معاكسة فلسفة كل استراتيجية.
# DAILY تبقى على الحارس الأصلي 1.8 (أعلى وزنًا استراتيجيًا، يستحق صرامة أكبر).
# [FER3ON-FIX-2026-08-19] رفع الحدود لمنع صفقات R:R معكوس (السبب الرئيسي للخسارة)
MIN_RR_GUARD_BY_STRATEGY = {
    "DAILY": 2.0,
    "SMC":   1.5,   # كان 0.9 — رُفع بعد إثبات R:R فعلي=0.67 خاسر
    "SCALP": 1.3,   # كان 0.85
    "MICRO": 1.4,   # كان 0.7 — رُفع بعد إثبات R:R فعلي=0.93 خاسر
}
# حد أدنى مطلق لا يُكسر تحت أي ظرف — رُفع من 0.6 إلى 1.2
MIN_RR_GUARD_ABSOLUTE_FLOOR = 1.2

# =============================================================================
# V3.6 — ADAPTIVE TRAILING STOP (مرن حسب الاستراتيجية + حالة المحاذاة)
# =============================================================================
# trailing_distance = ATR × BASE_MULT[strategy] × ALIGNMENT_FACTOR[mode]
# ALIGNED → مساحة تنفّس أكبر (يتبع الترند بثقة)
# CONFLICT → مسافة أضيق (حماية أسرع لرأس المال، بدون وقف الصفقة)
# =============================================================================

TRAILING_BASE_ATR_MULT = {
    "MICRO": 0.8,
    "SCALP": 1.0,
    "SMC":   1.5,
    "DAILY": 2.0,
}

TRAILING_ALIGNMENT_FACTOR = {
    "ALIGNED":  1.0,
    "NEUTRAL":  0.70,
    "CONFLICT": 0.55,
}

# V3.6: حد أدنى مطلق خاص بكل استراتيجية — يستبدل MIN_TRAIL العامة الواحدة
# (التي كانت تطغى على كل تمييز TRAILING_BASE_ATR_MULT عند ATR طبيعي/منخفض،
# لأن MIN_TRAIL=5.0 أعلى من atr×mult لكل الاستراتيجيات في الأحوال العادية).
# القيم أقل تدريجيًا للفريمات الأسرع (MICRO/SCALP) كي يبقى التمييز فعّالًا.
TRAILING_MIN_DISTANCE_BY_STRATEGY = {
    "MICRO": 2.0,
    "SCALP": 3.0,
    "SMC":   4.0,
    "DAILY": MIN_TRAIL,  # تبقى DAILY على الحد الأدنى العام الأصلي (الأكثر تحفظًا)
}

# SMC تحديدًا: التريلينج المتدرج لا يُفعَّل إلا بعد تحقق TP1 (حماية أولاً عبر break-even)
TRAILING_SMC_REQUIRES_TP1 = True

# =============================================================================
# V9 — SHADOW READINESS BRIDGE (analytics/v9_readiness_bridge.py)
# =============================================================================
# طبقة قراءة خارجية بالكامل لـ core/phase3/final_brain.py.readiness_score —
# لا تلمس أي ملف داخل core/phase3/ ولا الـ assert الذي يحرسه (متعمَّد بقوة:
# assert not FINAL_BRAIN_LIVE_AUTHORITY في core/phase3/final_brain.py).
#
# تأثير تدريجي صغير جدًا (لا ثنائي تشغيل/إيقاف): يبدأ من الصفر تحت
# V9_READINESS_MIN_SCORE_FOR_ANY_EFFECT، ويتدرّج خطيًا حتى السقف المطلق
# V9_READINESS_MAX_LOT_EFFECT عند readiness_score=100. حتى عند الجاهزية
# الكاملة، السقف يبقى صغيرًا متعمَّدًا (هامش حذر بشري دائم، لا تفعيل "كامل").
#
# الحالة الفعلية وقت الكتابة (راجع data/analytics/phase3/final_brain/
# final_brain_state.json): readiness_score≈61، false_reject_rate≈34%
# (أعلى من الحد المسموح 10%) — تحت العتبة الدنيا هنا (65)، فالتأثير الفعلي
# الآن = صفر تمامًا (1.0×) حتى تتحسن الأرقام طبيعيًا من مزيد من دورات Shadow.
# =============================================================================

V9_READINESS_BRIDGE_ENABLED = True

# تحت هذه القيمة: تأثير صفري تام (1.0×) — لا ثقة كافية حتى لتأثير صغير
V9_READINESS_MIN_SCORE_FOR_ANY_EFFECT = 65.0

# السقف المطلق للتكبير عند readiness_score=100 (مثلاً 0.05 = +5% فقط كحد أقصى
# حتى في أفضل حالة جاهزية ممكنة — متعمَّد الصغر، "غير متهور" بمعناه الحرفي)
V9_READINESS_MAX_LOT_EFFECT = 0.05

# =============================================================================
# V6 — QUANT ENGINE (analytics/quant_engine.py)
# =============================================================================
# الفلسفة: نفس مبدأ V3.6 (MTF Alignment) — لا حظر أبدًا، فقط تصغير. الأداء
# الضعيف لاستراتيجية معيّنة يُصغّر لوتها/وزنها تلقائيًا (QUANT_MIN_RISK_MULTIPLIER
# كحد أدنى مطلق لا يُكسر)، بدل إيقافها كليًا — قد يكون ضعف الأداء مؤقتًا
# (تغيّر سياق السوق) لا عيبًا بنيويًا دائمًا في الاستراتيجية.
# =============================================================================

# أقل عدد صفقات مطلوب قبل أن يُؤخذ تقييم الصحة بعين الاعتبار فعليًا — عيّنة
# أصغر من ذلك تُعطى وضعًا UNKNOWN (لا عقوبة ولا بونص، تحفّظ بدل تخمين)
QUANT_MIN_TRADES_FOR_HEALTH = 20

# الحدود المطلقة لمعامل الخطر الناتج عن تقييم الصحة — لا يصفّر اللوت أبدًا
QUANT_MIN_RISK_MULTIPLIER = 0.30
QUANT_MAX_RISK_MULTIPLIER = 1.25

# عتبات تصنيف الصحة (قابلة للتعديل دون لمس الكود) — Profit Factor + Sharpe
# (per-trade returns، انظر التوثيق المنهجي في رأس quant_engine.py)
QUANT_HEALTH_THRESHOLDS = {
    "excellent_pf": 2.0, "excellent_sharpe": 0.30,
    "good_pf":      1.5, "good_sharpe":      0.15,
    "neutral_pf":   1.1,
    "weak_pf":      0.8,
    # أقل من weak_pf → POOR
}

# =============================================================================
# FAIE — Phase-2 spec §5: Shadow-logging call site (docs/FAIE/PHASE_2_SPECIFICATION.md)
# =============================================================================
# LOGGING-ONLY. When True, core.fer3on_decision_authority.decide_trade() also
# runs brain.faie.ChiefDecisionOfficer on the same DecisionContext and appends
# the resulting advisory Decision to FAIE_SHADOW_LOG_PATH. This has zero
# effect on the real decision: it never raises, never blocks, never changes
# unified_decide()'s result — see brain/faie/shadow_logging.py.
#
# ENABLED BY EXPLICIT HUMAN DECISION on 2026-07-09 (see
# docs/FAIE/PHASE_2_PROGRESS.md, "Shadow logging enabled" section) — the
# account owner approved turning this on to start accumulating real decision
# history for certification.self_audit's bias/drift checks, which cannot
# produce anything beyond INSUFFICIENT_DATA without it. This is still purely
# a logging toggle: it does not enable Paper Trading, live execution
# influence, or any Volume 1 gate — those remain separate, explicitly
# human-approved steps. Override with the env var below if you ever need to
# disable it for a specific run without editing this file.
FAIE_SHADOW_LOGGING_ENABLED = os.getenv(
    'FAIE_SHADOW_LOGGING_ENABLED', 'True'
).lower() in ('true', '1', 'yes')

FAIE_SHADOW_LOG_PATH = 'data/faie/shadow_log.jsonl'

# =============================================================================
# FAIE — Phase-2 spec §3.3: Execution Quality Engine (post-trade)
# =============================================================================
# Pure observability — record_execution_outcome() only ever appends a row;
# it never influences lot sizing, gating, or order placement.
EXECUTION_QUALITY_CSV = 'data/analytics/execution_quality.csv'

# =============================================================================
# TP Capping validation telemetry (see TP_CAPPING_IMPLEMENTATION_REPORT.md
# §"gradual activation" recommendation — the cap itself is already live and
# unconditional; this just records every time it actually clips a TP so the
# planned 2-week live-data validation has real numbers to look at instead of
# nothing).
# =============================================================================
TP_CAP_MONITOR_CSV = 'data/analytics/tp_cap_events.csv'



# =============================================================================
# PHASE 4 — DECISION LEDGER + TRUTH ATTRIBUTION (logging only, safe)
# =============================================================================
# تسجيل قرار واحد غير قابل للتعديل لكل إشارة (signal→authority→entry→exit)
# موسوم بـ BUILD_ID + regime + session — لا يُقرأ في مسار القرار الحي أبدًا.
DECISION_LEDGER_ENABLED       = True
DECISION_LEDGER_LOG_PATH      = "data/analytics/decision_ledger/decisions.jsonl"
DECISION_LEDGER_OUTCOMES_PATH = "data/analytics/decision_ledger/outcomes.jsonl"

# =============================================================================
# PHASE 5 — OPPORTUNITY ALLOCATOR (LIVE ENABLED — 2026-08-31)
# Gradual sizing: EXCELLENT→GOOD→FAIR→WEAK for selective opportunity entry
# Reduces max drawdown by 84% while maintaining win rate (63.2%)
# =============================================================================
PHASE5_OPPORTUNITY_ALLOCATOR_ENABLED      = True
PHASE5_OPPORTUNITY_ALLOCATOR_PROMOTION_ENABLED = False
PHASE5_OPPORTUNITY_ALLOCATOR_LIVE_ENABLED = bool(
    ALLOW_LIVE_TRADING and PHASE5_OPPORTUNITY_ALLOCATOR_PROMOTION_ENABLED
)  # requires both global and explicit promotion approval
SECONDARY_STRATEGY_LIVE_AUTHORITY_ENABLED = False
PHASE5_ALLOCATOR_LOG_PATH                 = "data/analytics/opportunity_allocator/evaluations.jsonl"
ALLOCATOR_BASE_RISK_R                     = 0.25   # مخاطرة الفرصة العادية
ALLOCATOR_MIN_SCORE                       = 0.10   # أقل منها = SKIP
ALLOCATOR_GOOD_SCORE                      = 0.25   # +نتائج مثبتة → 0.50R
ALLOCATOR_EXCELLENT_SCORE                 = 0.40   # +نتائج مثبتة → 0.75R
ALLOCATOR_EXCEPTIONAL_SCORE               = 0.50   # الحد الوحيد المقبول في وضع PROTECTION
ALLOCATOR_MIN_SAMPLES                     = 30     # لا رفع مخاطرة قبل 30 نتيجة منسوبة
DAILY_PROFIT_LOCK_DOLLARS                 = 30.0   # Profit Lock: حماية ربح اليوم
DAILY_SURVIVAL_AFTER_LOSSES               = 2      # خسارتان متتاليتان → SURVIVAL
DAILY_STATE_MACHINE_ENABLED               = True

# Genetic evolution is research-only until it is backed by attributed,
# out-of-sample results and an explicit promotion review.
GENETIC_EVOLUTION_ENABLED                 = True
GENETIC_EVOLUTION_LIVE_INFLUENCE          = False
GENETIC_EVOLUTION_MIN_VALID_SAMPLES       = 100
