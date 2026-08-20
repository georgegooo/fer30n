from __future__ import annotations

from core.mt5_compat import mt5, MT5_AVAILABLE
from execution.multi_tp import (
    get_registered_ladder,
    next_pending_target,
    target_hit,
    mark_target_closed,
    forget_ticket,
)


def _round_volume(symbol: str, vol: float) -> float:
    try:
        info = mt5.symbol_info(symbol)
        step = float(getattr(info, 'volume_step', 0.01) or 0.01)
        # normalize to nearest step (floor to avoid over-close)
        steps = int((vol + 1e-9) // step)
        return max(step, round(steps * step, 2))
    except Exception:
        return round(max(0.0, float(vol)), 2)


def process_tp_ladders(symbol: str) -> None:
    """Periodic monitor: check registered TP ladders and perform partial closes.

    Called from `main.py`'s main loop after trailing updates.
    """
    if not MT5_AVAILABLE or mt5 is None:
        return

    try:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return

        positions = mt5.positions_get(symbol=symbol) or []
        if not positions:
            return

        for pos in positions:
            ticket = int(pos.ticket)
            ladder = get_registered_ladder(ticket)
            if not ladder or not ladder.get('enabled'):
                continue

            levels = ladder.get('levels', [])
            closed = ladder.get('closed_labels', [])
            next_level = next_pending_target(levels, closed)
            if not next_level:
                forget_ticket(ticket)
                continue

            pos_type = 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL'
            current_price = float(tick.bid if pos_type == 'BUY' else tick.ask)

            if target_hit(pos_type, current_price, float(next_level.get('price', 0.0))):
                total_vol = float(getattr(pos, 'volume', 0.0) or 0.0)
                base_volume = float(ladder.get('base_volume', total_vol) or total_vol)
                close_pct = float(next_level.get('close_pct', 0.0) or 0.0)
                target_volume = base_volume * close_pct
                close_vol = _round_volume(symbol, min(total_vol, target_volume))

                if close_vol <= 0.0 or total_vol <= 0.0:
                    mark_target_closed(ticket, next_level['label'])
                    if not next_pending_target(levels, ladder.get('closed_labels', [])):
                        forget_ticket(ticket)
                    continue

                # Opposite order type to reduce position
                close_type = mt5.ORDER_TYPE_SELL if pos_type == 'BUY' else mt5.ORDER_TYPE_BUY
                price = round(current_price, 5)

                req = {
                    'action': mt5.TRADE_ACTION_DEAL,
                    'symbol': symbol,
                    'volume': float(close_vol),
                    'type': close_type,
                    'position': ticket,
                    'price': price,
                    'deviation': 20,
                    'magic': int(getattr(pos, 'magic', 0) or 0),
                }

                try:
                    res = mt5.order_send(req)
                    ok = res is not None and getattr(res, 'retcode', None) == mt5.TRADE_RETCODE_DONE
                    if ok:
                        mark_target_closed(ticket, next_level['label'])
                        print(f"✅ PARTIAL_CLOSE | ticket={ticket} label={next_level['label']} vol={close_vol}")
                        if not next_pending_target(levels, ladder.get('closed_labels', [])):
                            forget_ticket(ticket)
                    else:
                        print(f"❌ PARTIAL_CLOSE_FAILED | ticket={ticket} label={next_level['label']} ret={getattr(res, 'retcode', None)}")
                except Exception as e:
                    print(f"❌ PARTIAL_CLOSE_EXCEPTION | ticket={ticket} label={next_level['label']} err={e}")

    except Exception as exc:
        print(f"⚠️ TP_MONITOR_FAILED: {exc}")
