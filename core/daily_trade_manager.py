from core.mt5_compat import mt5, MT5_AVAILABLE


# =========================================
# DAILY POSITION MANAGER
# =========================================

def manage_daily_positions(symbol):

    positions = mt5.positions_get(
        symbol=symbol
    )

    if positions is None:

        return

    # =========================================
    # GET DAILY CANDLES
    # =========================================

    rates = mt5.copy_rates_from_pos(

        symbol,

        mt5.TIMEFRAME_D1,

        0,

        3

    )

    if rates is None:

        return

    # آخر شمعة مغلقة
    previous_candle = rates[-2]

    previous_high = previous_candle['high']

    previous_low = previous_candle['low']

    # =========================================
    # LOOP POSITIONS
    # =========================================

    for position in positions:

        # DAILY ONLY
        # V3.6 FIX: الكومنت الحقيقي هو "F3_DAILY_A" لا "DAILY" — الفلتر
        # القديم (position.comment != "DAILY") كان دائمًا True، فهذا الفرع
        # كان معطّلاً بالكامل بسبب ده.
        #
        # AUDIT CORRECTION: الجملة القديمة هنا كانت بتقول إن V3.6 كمان ربط
        # الدالة دي (manage_daily_positions) بحلقة main الرئيسية — ده غير
        # صحيح فعليًا. manage_daily_positions() مش متنادية من main.py ولا
        # من أي حتة تانية في المشروع، ومفيش أي run_daily_cycle أو مسار حي
        # بيفتح صفقة DAILY جديدة أصلًا (DAILY_MAGIC معرّف بس من غير أي
        # caller). يعني الدالة دي كلها -- مش بس الفلتر -- dead code حاليًا:
        # لو اتنادت هتلاقي صفر مراكز بكومنت "F3_DAILY*" تدير الـ SL بتاعها.
        # لو حابب تفعّل DAILY فعليًا محتاج (1) مسار entry حقيقي يفتح صفقات
        # بكومنت "F3_DAILY..." و magic=DAILY_MAGIC، و(2) استدعاء
        # manage_daily_positions(SYMBOL) جوه حلقة main.py الرئيسية.
        if not str(position.comment or "").upper().startswith("F3_DAILY"):

            continue

        ticket = position.ticket

        current_sl = position.sl

        tp = position.tp

        # =========================================
        # BUY POSITION
        # =========================================

        if position.type == mt5.ORDER_TYPE_BUY:

            new_sl = previous_low

            # لا نقلل الحماية
            if current_sl != 0:

                if new_sl <= current_sl:

                    continue

        # =========================================
        # SELL POSITION
        # =========================================

        else:

            new_sl = previous_high

            # لا نقلل الحماية
            if current_sl != 0:

                if new_sl >= current_sl:

                    continue

        # =========================================
        # MODIFY REQUEST
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

            f"🌍 DAILY SL UPDATED | "

            f"Ticket: {ticket} | "

            f"New SL: {new_sl}"

        )

        print(result)