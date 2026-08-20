from core.mt5_compat import mt5, MT5_AVAILABLE
from core.scalp.trailing import update_scalp_trailing as _scalp_update_trailing


# =========================================
# TRAILING STOP
# =========================================


def update_scalp_trailing(symbol, atr):
    return _scalp_update_trailing(symbol, atr)


def update_trailing_stop(

    symbol,

    trailing_distance

):

    positions = mt5.positions_get(
        symbol=symbol
    )

    if positions is None:

        return

    for position in positions:

        # =========================================
        # SCALP ONLY (legacy single-shot trailing — called once at trade
        # open from trade_executor.py). V3.6 FIX: السكومنت الحقيقي المُولَّد
        # من core/mt5_order_utils.build_compact_order_comment هو بصيغة
        # "F3_SCALP_A" لا "SCALP" — الفلتر القديم (position.comment != "SCALP")
        # كان دائمًا True لأي صفقة فعليًا، فهذا الفرع كان معطّلاً بالكامل.
        # =========================================

        if not str(position.comment or "").upper().startswith("F3_SCALP"):

            continue

        ticket = position.ticket

        current_sl = position.sl

        tp = position.tp

        tick = mt5.symbol_info_tick(
            symbol
        )

        # =========================================
        # BUY
        # =========================================

        if position.type == mt5.ORDER_TYPE_BUY:

            current_price = tick.bid

            new_sl = (
                current_price
                - trailing_distance
            )

            if new_sl <= current_sl:

                continue

        # =========================================
        # SELL
        # =========================================

        else:

            current_price = tick.ask

            new_sl = (
                current_price
                + trailing_distance
            )

            if current_sl != 0:

                if new_sl >= current_sl:

                    continue

        # =========================================
        # MODIFY
        # =========================================

        request = {

            "action": mt5.TRADE_ACTION_SLTP,

            "symbol": symbol,

            "position": ticket,

            "sl": new_sl,

            "tp": tp

        }

        result = mt5.order_send(
            request
        )

        print(

            f"⚡ SCALP TRAILING "

            f"| Ticket: {ticket}"

        )

        print(result)
