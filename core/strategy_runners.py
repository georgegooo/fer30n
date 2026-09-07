# =============================================================================
# FER3ON AI V3.5 — INDEPENDENT STRATEGY RUNNERS (Phase-2.3)
# =============================================================================
# Previously, main.py only ever evaluated SMC. SCALP, SWING and MICRO engines
# existed in core/ but were never called by the live loop. This module gives
# each of them its own thin runner that:
#   1. Pulls the minimum data the strategy's own (unmodified) signal function
#      needs.
#   2. Asks the strategy's own engine for a signal — no strategy logic is
#      touched or reimplemented here.
#   3. Routes the candidate through the SAME hard gates SMC now uses:
#       Portfolio Risk Authority (evaluate_risk) -> execute_trade.
#   4. Tracks its own per-strategy cooldown and magic number.
#
# Each runner returns a small dict describing what happened, for logging in
# main.py. None of them raise on expected "no trade" conditions — only on
# genuinely unexpected errors, which are caught and reported, never silently
# swallowed.
# =============================================================================

from __future__ import annotations

import time
import threading
from typing import Any, Dict, Optional

from core.mt5_compat import MT5_AVAILABLE, mt5
from core.settings import (
    SYMBOL,
    SCALP_MAGIC,
    SWING_MAGIC,
    MICRO_MAGIC,
    MAX_LOT,
    MAX_SL_DISTANCE_DOLLARS,
    get_min_sl_dollars,
    BASE_RISK_SCALP,
    BASE_RISK_SWING,
    BASE_RISK_MICRO,
    SCALP_SESSIONS,
    SCALP_MAX_PER_SESSION,
    SCALP_MIN_QUALITY,
    SCALP_TP_ATR_MULT,
    SCALP_SL_ATR_MULT,
    SCALP_COOLDOWN_SEC,
    SWING_MAX_PER_DAY,
    SWING_MIN_QUALITY,
    SWING_TP_ATR_MULT,
    SWING_SL_ATR_MULT,
    MAX_SCALP_TRADES_PER_DAY,
    MAX_DAILY_SWING_TRADES_PER_DAY,
    MAX_MICRO_TRADES_PER_DAY,
    MAX_SAME_DIRECTION_POSITIONS,
    TP_ATR_CAP_MULT,
    TP_SL_MULT,
    get_tp_cap_multiplier,
    get_tp_sl_multiplier,
)
from core.atr_manager import calculate_atr
from core.portfolio_risk_authority import evaluate_risk, record_trade_open
from core.adaptive_floor import get_adaptive_floor
from core.adaptive_sl_tp_engine import calculate_adaptive_sl_tp
from core.risk_manager import calculate_smart_lot, evaluate_position_limits, get_loss_limits_status, compute_realized_risk_percent
from core.scalping_engine import get_scalping_signal
from core.swing_engine import get_swing_signal
from core.micro_trading_engine import should_enter_micro
from core.professional_swing_structure import analyze_swing_structure
from core.liquidity_intelligence import get_liquidity_bias


# =============================================================================
# Shared per-strategy cooldown + daily-count state (separate from SMC's,
# which lives in main.py — kept here so each runner is self-contained and
# importable/testable without importing main.py).
# THREAD SAFETY FIX #4: Protect _daily_count and _last_trade_time with lock
# to prevent race conditions when SCALP/SWING/MICRO runners execute in parallel.
# =============================================================================

_last_trade_time: Dict[str, float] = {}
_daily_count: Dict[str, int] = {}
_daily_count_day: Optional[str] = None
_runner_lock = threading.RLock()  # NEW: Reentrant lock for concurrent runners


def _today_key() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _reset_daily_if_needed() -> None:
    """Reset daily counters if date changed. MUST be called under _runner_lock."""
    global _daily_count_day, _daily_count
    today = _today_key()
    if _daily_count_day != today:
        _daily_count_day = today
        _daily_count = {}


def _cooldown_active(strategy: str, cooldown_sec: float) -> bool:
    """Check if strategy cooldown is still active. Thread-safe."""
    with _runner_lock:  # NEW: Lock before reading shared state
        last = _last_trade_time.get(strategy, 0.0)
        return (time.time() - last) < cooldown_sec


def _register_trade(strategy: str) -> None:
    """Record that a trade was opened for this strategy. Thread-safe."""
    global _last_trade_time, _daily_count
    with _runner_lock:  # NEW: Lock before modifying shared state
        _reset_daily_if_needed()
        _last_trade_time[strategy] = time.time()
        _daily_count[strategy] = _daily_count.get(strategy, 0) + 1


def _daily_count_for(strategy: str) -> int:
    """Get current day's trade count for strategy. Thread-safe."""
    with _runner_lock:  # NEW: Lock before reading shared state
        _reset_daily_if_needed()
        return _daily_count.get(strategy, 0)


def _calculate_exec_grade(quality_score: float, strategy: str = 'SMC') -> str:
    """
    [FER3ON-FIX-2026-09-02] حساب exec_grade ديناميكياً
    بدل من الثابت 'B' سابقاً
    
    الصيغة:
      - A+/A: جودة عالية (> 75%)
      - B+/B: جودة جيدة (55-75%)
      - C+/C: جودة متوسطة (35-55%)
      - D/F: جودة منخفضة (< 35%)
    """
    try:
        quality = float(quality_score or 50)
        
        if quality > 85:
            return 'A+'
        elif quality > 75:
            return 'A'
        elif quality > 65:
            return 'B+'
        elif quality > 55:
            return 'B'
        elif quality > 45:
            return 'C+'
        elif quality > 35:
            return 'C'
        else:
            return 'D'
    except Exception:
        return 'B'  # قيمة افتراضية آمنة


def _build_order_request_generic(signal: str, lot: float, sl_dist: float, tp_dist: float, atr: float = None, strategy: str = 'SCALP'):
    """Strategy-agnostic order request builder, mirroring main.py's
    _build_order_request but kept local to avoid a main.py <-> module import
    cycle (main.py is the entrypoint, not an importable library module)."""
    tick = mt5.symbol_info_tick(SYMBOL) if mt5 is not None else None
    point = 0.01
    if mt5 is not None:
        try:
            info = mt5.symbol_info(SYMBOL)
            if info:
                point = float(getattr(info, 'point', 0.01) or 0.01)
        except Exception:
            pass

    # [SLTP-4]: single, authoritative SL/TP finalization — see
    # core/sl_tp_finalizer.py. Replaces this function's previous local
    # reimplementation of the SL floor/cap (which, unlike
    # _enforce_min_stop_distance, never checked the broker's own
    # trade_stops_level — a second source of drift on top of the TP-vs-SL
    # ratio bug) plus a separate TP rescale + ATR-cap sequence.
    from core.sl_tp_finalizer import finalize_sl_tp

    original_sl_dist = float(sl_dist)
    original_tp_dist = float(tp_dist)
    final = finalize_sl_tp(
        symbol=SYMBOL,
        sl_dist_raw=sl_dist,
        tp_dist_raw=tp_dist,
        point=point,
        strategy=strategy,
        atr=atr,
        market_regime=None,
        confidence=1.0,
    )
    sl_dist = final['sl_dist']
    tp_dist = final['tp_dist']

    if sl_dist != original_sl_dist:
        print(f'🛡 SL_DIST_FIXED_GENERIC | was={original_sl_dist} → now={sl_dist}')
    if tp_dist != original_tp_dist:
        print(f'🛡 TP_ADJUSTED_GENERIC | was={original_tp_dist:.2f} → now={tp_dist:.2f} | rr={final["rr"]}')
    if final['tp_was_atr_capped']:
        try:
            from analytics.tp_cap_monitor import record_tp_cap_event
            strat = str(strategy or 'SCALP').upper()
            record_tp_cap_event(
                strategy=strat, signal=signal, atr=atr, sl_dist=sl_dist,
                tp_dist_requested=original_tp_dist, tp_dist_capped=tp_dist,
                cap_multiplier_atr=float(get_tp_cap_multiplier(strat)),
                cap_multiplier_sl=float(get_tp_sl_multiplier(strat)),
            )
        except Exception as _tp_log_err:
            print(f'⚠️ TP_CAP_MONITOR_LOG_FAILED (non-fatal): {_tp_log_err}')

    if str(signal).upper() == 'SELL':
        order_type = mt5.ORDER_TYPE_SELL
        price = float(getattr(tick, 'bid', 0.0) or 0.0)
        # sl_dist/tp_dist are raw price units — used directly, not * point
        # (see [SLTP-1]; matches core/trailing_stop.py's convention).
        sl = round(price + sl_dist, 5)
        tp = round(price - tp_dist, 5)
    else:
        order_type = mt5.ORDER_TYPE_BUY
        price = float(getattr(tick, 'ask', 0.0) or 0.0)
        sl = round(price - sl_dist, 5)
        tp = round(price + tp_dist, 5)

    return {
        'symbol': SYMBOL,
        'volume': float(lot),
        'type': order_type,
        'price': price,
        'sl': sl,
        'tp': tp,
        'deviation': 20,
        'type_time': mt5.ORDER_TIME_GTC,
        'action': mt5.TRADE_ACTION_DEAL,
    }


def _execute(*, strategy: str, signal: str, lot: float, sl_dist: float, tp_dist: float,
             risk_percent: float, quality_score: float, session: str, market_regime: str,
             atr: float, magic: int, rates=None, tp_tiers=None,
             structure_analysis: dict = None, liquidity: dict = None,
             risk_decision=None):
    """Shared tail-end: build request, call execute_trade, record on success.

    V7 INTEGRATION (core/v7_integration.py — Execution Intelligence): يحسب
    velocity bonus من ``rates`` (إن توفرت) ويُمرَّر كـ confidence bonus إضافي
    لـ execute_trade. كود v7_integration كان موجودًا وناضجًا مسبقًا لكنه غير
    متصل بـ main.py على الإطلاق (انظر التوثيق الكامل في core/trade_executor.py
    حول هذا الاكتشاف). ``rates=None`` (الافتراضي) = سلوك مطابق تمامًا للسابق،
    لا كسر لأي استدعاء قديم لم يُمرِّر rates.
    """
    from core.trade_executor import execute_trade  # local import: avoid import-time MT5 dependency at module load

    # =========================================================================
    # FER3ON FINAL [EXPOSURE-2]: same-direction concentration cap, ported from
    # main.py's SMC path so SCALP/SWING/MICRO get the same protection instead
    # of only being bounded by the (direction-blind) MAX_OPEN_TRADES count.
    # Checks LIVE MT5 positions on the symbol, so it is inherently
    # cross-strategy — a SCALP long and a SWING long both count together.
    # [SAFETY-1]: positions_get() returning None means MT5 state unknown.
    # Fail-closed: treat None as a hard block, never assume zero positions.
    # =========================================================================
    if mt5 is not None:
        try:
            positions = mt5.positions_get(symbol=SYMBOL)
            # FER3ON FINAL [SAFETY-1]: positions_get() returned None means MT5 state is unknown.
            # This is not "safe to proceed" — it's "data unavailable, must not trade".
            # Fail-closed: treat None as a hard block, never assume zero positions.
            if positions is None:
                print(f'🛑 {strategy} POSITION_CHECK_FAILED | MT5 state unknown, blocking trade (fail-closed)')
                return {'opened': False, 'reason': 'POSITION_CHECK_FAILED'}
            
            same_direction_count = 0
            for pos in positions:
                if signal == 'BUY' and pos.type == mt5.POSITION_TYPE_BUY:
                    same_direction_count += 1
                elif signal == 'SELL' and pos.type == mt5.POSITION_TYPE_SELL:
                    same_direction_count += 1
            if same_direction_count >= MAX_SAME_DIRECTION_POSITIONS:
                print(
                    f'🚫 {strategy} MAX SAME DIRECTION REACHED '
                    f'({same_direction_count}/{MAX_SAME_DIRECTION_POSITIONS})'
                )
                return {'opened': False, 'reason': 'MAX_SAME_DIRECTION_REACHED'}
        except Exception as exc:
            print(f'🛑 {strategy} SAME_DIRECTION_CHECK_FAILED (fail-closed): {exc}')
            return {'opened': False, 'reason': 'POSITION_STATE_UNAVAILABLE'}

    # V7: velocity bonus — fail-safe كامل، لا يمنع الصفقة أبدًا عند أي خطأ
    v7_confidence_bonus = 0.0
    if rates is not None:
        try:
            from core.v7_integration import v7_enabled
            from core.velocity_engine import analyze_velocity_from_closes
            if v7_enabled():
                closes = [float(r['close']) for r in rates]
                velocity_result = analyze_velocity_from_closes(closes, atr)
                v7_confidence_bonus = float(velocity_result.get('confidence_bonus', 0.0) or 0.0)
        except Exception as exc:
            print(f'⚠️ V7_VELOCITY_BONUS_FAILED (non-fatal, bonus=0): {exc}')
            v7_confidence_bonus = 0.0

    # Best-effort enrichment (§ ai_memory enrichment fix): SCALP/SWING/MICRO
    # don't run the full SMC decision pipeline, but when a caller has already
    # computed structure_analysis (SWING does) or we can cheaply derive a
    # liquidity bias here, log it the same way SMC does. Never fabricated —
    # left as None (unlogged) when genuinely unavailable, and never allowed
    # to block a trade if the lookup fails.
    _choch_state = _choch_strength = _liq_map_score = _liq_map_dir = None
    if structure_analysis:
        _choch_state = structure_analysis.get('choch')
        _choch_strength = structure_analysis.get('choch_strength')
    if liquidity is None:
        try:
            liquidity = get_liquidity_bias(SYMBOL)
        except Exception as exc:
            print(f'⚠️ LIQUIDITY_BIAS_LOOKUP_FAILED (non-fatal): {exc}')
            liquidity = None
    if liquidity:
        _liq_map_score = liquidity.get('score', 0)
        _liq_bias = liquidity.get('bias')
        _liq_map_dir = 'UP' if _liq_bias == 'BUY' else 'DOWN' if _liq_bias == 'SELL' else 'NEUTRAL'

    # HIGH FIX #6: Validate SL/TP before building request
    if sl_dist is None or float(sl_dist or 0) <= 0:
        print(f'🛑 {strategy} SL/TP_VALIDATION_FAILED | Invalid SL distance: {sl_dist}')
        return {'opened': False, 'reason': 'INVALID_SL_DISTANCE'}
    if tp_dist is None or float(tp_dist or 0) <= 0:
        print(f'🛑 {strategy} SL/TP_VALIDATION_FAILED | Invalid TP distance: {tp_dist}')
        return {'opened': False, 'reason': 'INVALID_TP_DISTANCE'}

    request = _build_order_request_generic(signal, lot, sl_dist, tp_dist, atr=atr, strategy=strategy)
    result = execute_trade(
        request=request,
        strategy=strategy,
        signal=signal,
        lot=lot,
        sl_dist=sl_dist,
        tp_dist=tp_dist,
        rr_ratio=round(tp_dist / sl_dist, 2) if sl_dist else 0,
        risk_percent=float(getattr(risk_decision, 'final_risk_percent', risk_percent) or risk_percent),
        exec_grade=_calculate_exec_grade(quality_score, strategy),
        final_brain={'final_score': quality_score},
        quality_score=quality_score,
        confidence={'pct': quality_score},
        market_regime=market_regime,
        atr=atr,
        session=session,
        magic=magic,
        tp_tiers=tp_tiers,
        v7_confidence_bonus=v7_confidence_bonus,
        choch_state=_choch_state,
        choch_strength=_choch_strength,
        liq_map_score=_liq_map_score,
        liq_map_dir=_liq_map_dir,
    )

    if result is not None and getattr(result, 'retcode', None) == mt5.TRADE_RETCODE_DONE:
        print(f'✅ {strategy} TRADE OPENED | ticket={result.order} lot={lot}')
        _register_trade(strategy)
        try:
            _entry_price_val = float(getattr(result, 'price', 0) or 0)
            _sl_price_val = float(request.get('sl', 0) or 0)
            _realized_risk_pct = compute_realized_risk_percent(
                lot=float(lot),
                entry_price=_entry_price_val,
                sl_price=_sl_price_val,
                balance=_account_balance(),
            )
            record_trade_open(
                ticket=int(result.order),
                strategy=strategy,
                direction=signal,
                lot=float(lot),
                # FER3ON FINAL [EXPOSURE-1]: actual realized risk, not nominal
                # pre-sizing risk_percent — see FER3ON_FINAL_CHANGELOG.md.
                risk_percent=_realized_risk_pct,
                entry_price=_entry_price_val,
                sl=_sl_price_val,
                tp=float(request.get('tp', 0) or 0),
                symbol=SYMBOL,
                meta={'quality_score': quality_score, 'session': session},
            )
        except Exception as exc:
            print(f'⚠️ record_trade_open failed for {strategy}: {exc}')
        return {'opened': True, 'ticket': result.order, 'lot': lot}

    print(f'{strategy} execution skipped: order not filled (retcode={getattr(result, "retcode", None)})')
    return {'opened': False, 'reason': 'EXECUTION_FAILED'}


def _account_balance() -> float | None:
    from core.settings import BASE_ACCOUNT_BALANCE
    try:
        account = mt5.account_info() if mt5 is not None else None
        bal = float(getattr(account, 'balance', 0) or 0)
        return bal if bal > 0 else None
    except Exception:
        return None


def _position_counts(strategy_key: str) -> tuple:
    """Return (current_count, total_count) for position evaluation.
    
    [SAFETY-1]: If positions_get() fails or returns None, this returns (0,0)
    which allows the position limit check to pass, but the trade will be
    blocked downstream by POSITION_CHECK_FAILED in the _execute() path.
    """
    try:
        positions = mt5.positions_get(symbol=SYMBOL) if mt5 is not None else []
        positions = positions or []
        return len(positions), len(positions)
    except Exception:
        return None, None


def _allocator_gate(*, strategy: str, quality_score: float,
                    confidence_pct: float, market_regime: str,
                    session: str) -> tuple[bool, float, str]:
    """Apply the opportunity allocator independently per strategy."""
    try:
        from core.opportunity_allocator import rank_opportunity
        from core.settings import (
            PHASE5_OPPORTUNITY_ALLOCATOR_LIVE_ENABLED,
            PHASE5_ADVISORY_WEAK_RISK_MULTIPLIER,
        )
        rank = rank_opportunity(
            quality_score=float(quality_score),
            confidence_pct=float(confidence_pct),
            market_regime=market_regime,
            session=session,
            smc_strength=0.0,
            mtf_strength=0,
            execution_grade='B',
            daily_bias_alignment=False,
        )
        if rank.should_reject:
            if PHASE5_OPPORTUNITY_ALLOCATOR_LIVE_ENABLED:
                return False, 0.0, f'ALLOCATOR_REJECT:{rank.reasoning}'
            return True, PHASE5_ADVISORY_WEAK_RISK_MULTIPLIER, f'ALLOCATOR_ADVISORY_WEAK:{rank.reasoning}'
        return True, float(rank.risk_adjustment), rank.reasoning
    except Exception as exc:
        return False, 0.0, f'ALLOCATOR_CHECK_FAILED:{type(exc).__name__}'


# =============================================================================
# SCALP RUNNER
# =============================================================================

def run_scalp_cycle(*, session: str, market_regime: str = 'UNKNOWN') -> Dict[str, Any]:
    if not MT5_AVAILABLE or mt5 is None:
        return {'opened': False, 'reason': 'MT5_UNAVAILABLE'}

    # User request: allow SCALP to evaluate at any time, instead of being
    # blocked by a hard session whitelist.
    # The strategy still keeps all other risk/cooldown/quality gates.

    if _daily_count_for('SCALP') >= MAX_SCALP_TRADES_PER_DAY:
        return {'opened': False, 'reason': 'DAILY_CAP_HIT'}

    if _cooldown_active('SCALP', SCALP_COOLDOWN_SEC):
        return {'opened': False, 'reason': 'COOLDOWN_ACTIVE'}

    try:
        signal = get_scalping_signal(SYMBOL)
    except Exception as exc:
        return {'opened': False, 'reason': f'SIGNAL_ERROR:{exc}'}

    if signal not in ('BUY', 'SELL'):
        return {'opened': False, 'reason': 'NO_SIGNAL'}

    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 60)
    if rates is None or len(rates) < 20:
        return {'opened': False, 'reason': 'NO_RATES'}
    atr = float(calculate_atr(rates) or 0.0)
    if atr <= 0:
        return {'opened': False, 'reason': 'ATR_INVALID'}

    quality_score = SCALP_MIN_QUALITY
    adaptive_floor = get_adaptive_floor('SCALP', session=session)
    if quality_score < adaptive_floor:
        return {'opened': False, 'reason': f'BELOW_ADAPTIVE_FLOOR({quality_score}<{adaptive_floor})'}

    risk_percent = BASE_RISK_SCALP
    adaptive = calculate_adaptive_sl_tp(
        atr=atr,
        strategy='SCALP',
        lot=0.01,
        confidence=quality_score / 100.0,
        quality_score=quality_score,
        market_regime=market_regime,
        session=session,
        structure_strength=0.7,
        liquidity=0.7,
        volatility=0.4,
        spread=0.0,
        execution_grade='B',
        broker_stop_level=0.0,
        broker_stop_fallback=0.0,
        min_sl=get_min_sl_dollars(),  # [REARCH-1]: single source of truth, see core/settings.py
    )
    sl_dist = adaptive['sl_distance']
    tp_dist = adaptive['tp_distance']

    allowed, allocator_multiplier, allocator_reason = _allocator_gate(
        strategy='SCALP', quality_score=quality_score, confidence_pct=quality_score,
        market_regime=market_regime, session=session,
    )
    if not allowed:
        return {'opened': False, 'reason': allocator_reason}
    risk_percent *= allocator_multiplier

    current_positions, total_positions = _position_counts('SCALP')
    if current_positions is None or total_positions is None:
        return {'opened': False, 'reason': 'POSITION_STATE_UNAVAILABLE'}
    pos_limit = evaluate_position_limits(strategy='SCALP', current_positions=current_positions, total_positions=total_positions)
    if not pos_limit.get('allowed', True):
        return {'opened': False, 'reason': pos_limit.get('reason')}

    balance = _account_balance()
    if balance is None:
        return {'opened': False, 'reason': 'ACCOUNT_BALANCE_UNAVAILABLE'}
    loss_limits = get_loss_limits_status(balance=balance)
    if loss_limits.get('daily_used', 0) >= loss_limits.get('daily_limit', 0):
        return {'opened': False, 'reason': 'DAILY_LOSS_CAPPED'}

    risk_decision = evaluate_risk(
        strategy='SCALP',
        direction=signal,
        requested_risk_percent=risk_percent,
        candidate_meta={'symbol': SYMBOL},
    )
    try:
        from analytics.authority_impact import record_risk_decision
        record_risk_decision(strategy='SCALP', direction=signal,
                              requested_risk_percent=risk_percent, decision=risk_decision)
    except Exception as _impact_log_err:
        print(f'⚠️ AUTHORITY_IMPACT_LOG_FAILED (non-fatal): {_impact_log_err}')
    if not risk_decision.approved:
        return {'opened': False, 'reason': risk_decision.rejection_reason}

    lot, _, _ = calculate_smart_lot(
        balance=balance,
        risk_percent=float(getattr(risk_decision, 'final_risk_percent', risk_percent) or risk_percent),
        sl_dist=sl_dist,
        symbol=SYMBOL,
        quality_score=quality_score,
        session=session,
        strategy='SCALP',
        market_regime=market_regime,
        size_mode='REDUCED',
    )
    lot = min(lot, MAX_LOT)
    tp_tiers = None
    if lot > 0:
        adaptive = calculate_adaptive_sl_tp(
            atr=atr,
            strategy='SCALP',
            lot=lot,
            confidence=quality_score / 100.0,
            quality_score=quality_score,
            market_regime=market_regime,
            session=session,
            structure_strength=0.7,
            liquidity=0.7,
            volatility=0.4,
            spread=0.0,
            execution_grade='B',
            broker_stop_level=0.0,
            broker_stop_fallback=0.0,
            min_sl=get_min_sl_dollars(),  # [REARCH-1]: single source of truth, see core/settings.py
        )
        sl_dist = adaptive['sl_distance']
        tp_dist = adaptive['tp_distance']
        tp_tiers = adaptive.get('tp_tiers')
    if lot <= 0:
        return {'opened': False, 'reason': 'LOT_ZERO'}

    try:
        structure_analysis = analyze_swing_structure(rates, current_price=float(rates[-1].get('close', 0.0) or 0.0))
    except Exception:
        structure_analysis = None

    return _execute(
        strategy='SCALP', signal=signal, lot=lot, sl_dist=sl_dist, tp_dist=tp_dist,
        risk_percent=risk_percent, quality_score=quality_score, session=session,
        market_regime=market_regime, atr=atr, magic=SCALP_MAGIC, rates=rates,
        tp_tiers=tp_tiers, structure_analysis=structure_analysis,
        risk_decision=risk_decision,
    )


# =============================================================================
# SWING RUNNER
# =============================================================================

def run_swing_cycle(*, session: str, market_regime: str = 'UNKNOWN') -> Dict[str, Any]:
    if not MT5_AVAILABLE or mt5 is None:
        return {'opened': False, 'reason': 'MT5_UNAVAILABLE'}

    if _daily_count_for('SWING') >= min(SWING_MAX_PER_DAY, MAX_DAILY_SWING_TRADES_PER_DAY):
        return {'opened': False, 'reason': 'DAILY_CAP_HIT'}

    try:
        signal = get_swing_signal(SYMBOL)
    except Exception as exc:
        return {'opened': False, 'reason': f'SIGNAL_ERROR:{exc}'}

    if signal not in ('BUY', 'SELL'):
        return {'opened': False, 'reason': 'NO_SIGNAL'}

    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 60)
    if rates is None or len(rates) < 20:
        return {'opened': False, 'reason': 'NO_RATES'}
    atr = float(calculate_atr(rates) or 0.0)
    if atr <= 0:
        return {'opened': False, 'reason': 'ATR_INVALID'}

    structure_analysis = analyze_swing_structure(rates, current_price=float(rates[-1].get('close', 0.0) or 0.0))

    quality_score = SWING_MIN_QUALITY
    adaptive_floor = get_adaptive_floor('SWING', session=session)
    if quality_score < adaptive_floor:
        return {'opened': False, 'reason': f'BELOW_ADAPTIVE_FLOOR({quality_score}<{adaptive_floor})'}

    adaptive = calculate_adaptive_sl_tp(
        atr=atr,
        strategy='SWING',
        lot=0.01,
        confidence=quality_score / 100.0,
        quality_score=quality_score,
        market_regime=market_regime,
        session=session,
        structure_strength=0.75,
        liquidity=0.7,
        volatility=0.45,
        spread=0.0,
        execution_grade='B',
        broker_stop_level=0.0,
        broker_stop_fallback=0.0,
        min_sl=get_min_sl_dollars(),  # [REARCH-1]: single source of truth, see core/settings.py
        structure_analysis=structure_analysis,
    )
    sl_dist = adaptive['sl_distance']
    tp_dist = adaptive['tp_distance']

    allowed, allocator_multiplier, allocator_reason = _allocator_gate(
        strategy='SWING', quality_score=quality_score, confidence_pct=quality_score,
        market_regime=market_regime, session=session,
    )
    if not allowed:
        return {'opened': False, 'reason': allocator_reason}
    risk_percent = BASE_RISK_SWING * allocator_multiplier

    current_positions, total_positions = _position_counts('SWING')
    if current_positions is None or total_positions is None:
        return {'opened': False, 'reason': 'POSITION_STATE_UNAVAILABLE'}
    # AUDIT FIX: was strategy='DAILY' -- a copy-paste leftover that checked
    # SWING's own position count against DAILY's limit instead of SWING's
    # (compare run_scalp_cycle/run_micro_cycle above, which correctly pass
    # their own names). See core/risk_manager.py's evaluate_position_limits
    # for the now-added 'SWING' entry this depends on.
    pos_limit = evaluate_position_limits(strategy='SWING', current_positions=current_positions, total_positions=total_positions)
    if not pos_limit.get('allowed', True):
        return {'opened': False, 'reason': pos_limit.get('reason')}

    balance = _account_balance()
    if balance is None:
        return {'opened': False, 'reason': 'ACCOUNT_BALANCE_UNAVAILABLE'}
    loss_limits = get_loss_limits_status(balance=balance)
    if loss_limits.get('daily_used', 0) >= loss_limits.get('daily_limit', 0):
        return {'opened': False, 'reason': 'DAILY_LOSS_CAPPED'}

    risk_decision = evaluate_risk(
        strategy='SWING',
        direction=signal,
        requested_risk_percent=risk_percent,
        candidate_meta={'symbol': SYMBOL},
    )
    try:
        from analytics.authority_impact import record_risk_decision
        record_risk_decision(strategy='SWING', direction=signal,
                              requested_risk_percent=risk_percent, decision=risk_decision)
    except Exception as _impact_log_err:
        print(f'⚠️ AUTHORITY_IMPACT_LOG_FAILED (non-fatal): {_impact_log_err}')
    if not risk_decision.approved:
        return {'opened': False, 'reason': risk_decision.rejection_reason}

    lot, _, _ = calculate_smart_lot(
        balance=balance,
        risk_percent=float(getattr(risk_decision, 'final_risk_percent', risk_percent) or risk_percent),
        sl_dist=sl_dist,
        symbol=SYMBOL,
        quality_score=quality_score,
        session=session,
        strategy='SWING',
        market_regime=market_regime,
        size_mode='REDUCED',
    )
    lot = min(lot, MAX_LOT)
    tp_tiers = None
    if lot > 0:
        adaptive = calculate_adaptive_sl_tp(
            atr=atr,
            strategy='SWING',
            lot=lot,
            confidence=quality_score / 100.0,
            quality_score=quality_score,
            market_regime=market_regime,
            session=session,
            structure_strength=0.75,
            liquidity=0.7,
            volatility=0.45,
            spread=0.0,
            execution_grade='B',
            broker_stop_level=0.0,
            broker_stop_fallback=0.0,
            min_sl=get_min_sl_dollars(),  # [REARCH-1]: single source of truth, see core/settings.py
            structure_analysis=structure_analysis,
        )
        sl_dist = adaptive['sl_distance']
        tp_dist = adaptive['tp_distance']
        tp_tiers = adaptive.get('tp_tiers')
    if lot <= 0:
        return {'opened': False, 'reason': 'LOT_ZERO'}

    return _execute(
        strategy='SWING', signal=signal, lot=lot, sl_dist=sl_dist, tp_dist=tp_dist,
        risk_percent=risk_percent, quality_score=quality_score, session=session,
        market_regime=market_regime, atr=atr, magic=SWING_MAGIC, rates=rates,
        tp_tiers=tp_tiers, structure_analysis=structure_analysis,
        risk_decision=risk_decision,
    )


# =============================================================================
# MICRO RUNNER
# =============================================================================

def run_micro_cycle(*, session: str, market_regime: str = 'UNKNOWN', confidence_pct: float = 50.0) -> Dict[str, Any]:
    try:
        from core.settings import MICRO_STRATEGY_ENABLED
    except Exception:
        MICRO_STRATEGY_ENABLED = False

    if not MICRO_STRATEGY_ENABLED:
        return {'opened': False, 'reason': 'MICRO_DISABLED_BY_POLICY'}

    if not MT5_AVAILABLE or mt5 is None:
        return {'opened': False, 'reason': 'MT5_UNAVAILABLE'}

    if _daily_count_for('MICRO') >= MAX_MICRO_TRADES_PER_DAY:
        return {'opened': False, 'reason': 'DAILY_CAP_HIT'}

    if _cooldown_active('MICRO', SCALP_COOLDOWN_SEC):  # MICRO shares the fast scalp-style cooldown
        return {'opened': False, 'reason': 'COOLDOWN_ACTIVE'}

    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 10)
    if rates is None or len(rates) < 3:
        return {'opened': False, 'reason': 'NO_RATES'}
    rates_list = [
        {'open': r['open'], 'high': r['high'], 'low': r['low'], 'close': r['close']}
        for r in rates
    ]

    try:
        approved, micro_result = should_enter_micro(rates_list, context={'confidence': confidence_pct})
    except Exception as exc:
        return {'opened': False, 'reason': f'SIGNAL_ERROR:{exc}'}

    if not approved:
        return {'opened': False, 'reason': 'NOT_APPROVED', 'detail': micro_result.get('reasons')}

    signal = micro_result.get('direction', 'NONE')
    if signal not in ('BUY', 'SELL'):
        return {'opened': False, 'reason': 'NO_DIRECTION'}

    atr = float(calculate_atr(rates) or 0.0)
    if atr <= 0:
        return {'opened': False, 'reason': 'ATR_INVALID'}

    quality_score = float(micro_result.get('score', 0) or 0)
    adaptive = calculate_adaptive_sl_tp(
        atr=atr,
        strategy='MICRO',
        lot=0.01,
        confidence=quality_score / 10.0,
        quality_score=quality_score,
        market_regime=market_regime,
        session=session,
        structure_strength=0.6,
        liquidity=0.6,
        volatility=0.35,
        spread=0.0,
        execution_grade='B',
        broker_stop_level=0.0,
        broker_stop_fallback=0.0,
        min_sl=get_min_sl_dollars(),  # [REARCH-1]: single source of truth, see core/settings.py
    )
    sl_dist = adaptive['sl_distance']
    tp_dist = adaptive['tp_distance']

    micro_quality = min(100.0, quality_score * 10.0)
    allowed, allocator_multiplier, allocator_reason = _allocator_gate(
        strategy='MICRO', quality_score=micro_quality,
        confidence_pct=confidence_pct, market_regime=market_regime, session=session,
    )
    if not allowed:
        return {'opened': False, 'reason': allocator_reason}
    risk_percent = BASE_RISK_MICRO * allocator_multiplier

    current_positions, total_positions = _position_counts('MICRO')
    if current_positions is None or total_positions is None:
        return {'opened': False, 'reason': 'POSITION_STATE_UNAVAILABLE'}
    pos_limit = evaluate_position_limits(strategy='MICRO', current_positions=current_positions, total_positions=total_positions)
    if not pos_limit.get('allowed', True):
        return {'opened': False, 'reason': pos_limit.get('reason')}

    balance = _account_balance()
    if balance is None:
        return {'opened': False, 'reason': 'ACCOUNT_BALANCE_UNAVAILABLE'}
    loss_limits = get_loss_limits_status(balance=balance)
    if loss_limits.get('daily_used', 0) >= loss_limits.get('daily_limit', 0):
        return {'opened': False, 'reason': 'DAILY_LOSS_CAPPED'}

    # NOTE: MICRO's internal score is a small additive integer (typically
    # 0-9, see micro_trading_engine.py), not a 0-100 composite like
    # SCALP/SWING/SMC. Applying the same 40-85 adaptive_floor scale to it
    # would be a category error, so it's deliberately not gated here.
    risk_decision = evaluate_risk(
        strategy='MICRO',
        direction=signal,
        requested_risk_percent=risk_percent,
        candidate_meta={'symbol': SYMBOL},
    )
    try:
        from analytics.authority_impact import record_risk_decision
        record_risk_decision(strategy='MICRO', direction=signal,
                              requested_risk_percent=risk_percent, decision=risk_decision)
    except Exception as _impact_log_err:
        print(f'⚠️ AUTHORITY_IMPACT_LOG_FAILED (non-fatal): {_impact_log_err}')
    if not risk_decision.approved:
        return {'opened': False, 'reason': risk_decision.rejection_reason}

    lot, _, _ = calculate_smart_lot(
        balance=balance,
        risk_percent=float(getattr(risk_decision, 'final_risk_percent', risk_percent) or risk_percent),
        sl_dist=sl_dist,
        symbol=SYMBOL,
        quality_score=quality_score,
        session=session,
        strategy='MICRO',
        market_regime=market_regime,
        size_mode='MICRO',
    )
    lot = min(lot, MAX_LOT)
    tp_tiers = None
    if lot > 0:
        adaptive = calculate_adaptive_sl_tp(
            atr=atr,
            strategy='MICRO',
            lot=lot,
            confidence=quality_score / 10.0,
            quality_score=quality_score,
            market_regime=market_regime,
            session=session,
            structure_strength=0.6,
            liquidity=0.6,
            volatility=0.35,
            spread=0.0,
            execution_grade='B',
            broker_stop_level=0.0,
            broker_stop_fallback=0.0,
            min_sl=get_min_sl_dollars(),  # [REARCH-1]: single source of truth, see core/settings.py
        )
        sl_dist = adaptive['sl_distance']
        tp_dist = adaptive['tp_distance']
        tp_tiers = adaptive.get('tp_tiers')
    if lot <= 0:
        return {'opened': False, 'reason': 'LOT_ZERO'}

    try:
        structure_analysis = analyze_swing_structure(rates_list, current_price=float(rates_list[-1].get('close', 0.0) or 0.0))
    except Exception:
        structure_analysis = None

    return _execute(
        strategy='MICRO', signal=signal, lot=lot, sl_dist=sl_dist, tp_dist=tp_dist,
        risk_percent=risk_percent, quality_score=quality_score, session=session,
        market_regime=market_regime, atr=atr, magic=MICRO_MAGIC, rates=rates,
        tp_tiers=tp_tiers, structure_analysis=structure_analysis,
        risk_decision=risk_decision,
    )


STRATEGY_RUNNERS = {
    'SCALP': run_scalp_cycle,
    'SWING': run_swing_cycle,
    'MICRO': run_micro_cycle,
}
