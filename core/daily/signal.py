from core.mt5_compat import mt5, MT5_AVAILABLE

from core.utils import (
    calculate_ema
)


# =========================================
# TREND DIRECTION
# =========================================

def trend_direction(rates):

    closes = [

        candle['close']

        for candle in rates

    ]

    # FIX 5: EMA صحيح ✅
    ema_fast = calculate_ema(closes, 20)

    ema_slow = calculate_ema(closes, 50)

    if ema_fast > ema_slow:

        return "BUY"

    elif ema_fast < ema_slow:

        return "SELL"

    return "NONE"


# =========================================
# SIMPLE PRICE ACTION
# =========================================

def candle_signal(rates):

    last = rates[-1]

    body = abs(

        last['close']

        - last['open']

    )

    candle_range = (

        last['high']

        - last['low']

    )

    if (

        last['close'] > last['open']

        and body > candle_range * 0.6

    ):

        return "BUY"

    elif (

        last['close'] < last['open']

        and body > candle_range * 0.6

    ):

        return "SELL"

    return "NONE"


# =========================================
# DAILY SIGNAL
# =========================================

def get_daily_signal(symbol):

    daily_rates = mt5.copy_rates_from_pos(

        symbol,

        mt5.TIMEFRAME_D1,

        0,

        100

    )

    h4_rates = mt5.copy_rates_from_pos(

        symbol,

        mt5.TIMEFRAME_H4,

        0,

        100

    )

    if (

        daily_rates is None

        or h4_rates is None

    ):

        return "NONE"

    daily_bias = trend_direction(
        daily_rates
    )

    h4_signal = candle_signal(
        h4_rates
    )

    if (

        daily_bias == "BUY"

        and h4_signal == "BUY"

    ):

        return "BUY"

    elif (

        daily_bias == "SELL"

        and h4_signal == "SELL"

    ):

        return "SELL"

    return "NONE"

def get_daily_bias(symbol):

    daily_rates = mt5.copy_rates_from_pos(
        symbol,
        mt5.TIMEFRAME_D1,
        0,
        100
    )

    if daily_rates is None:
        return "NONE"

    return trend_direction(
        daily_rates
    )
