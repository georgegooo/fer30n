"""Recovery cooldown and re-entry intelligence for FER3ON."""

from __future__ import annotations

from typing import Any, Dict
import time


def build_cooldown_state(
    recent_losses: int = 0,
    drawdown: float = 0.0,
    volatility: float = 0.0,
    loss_amount: float = 0.0,
    session: str = "UNKNOWN",
    recovery_state: str = "NONE",
    now: float | None = None,
) -> Dict[str, Any]:
    now_ts = float(now if now is not None else time.time())
    recovery = (recovery_state or "NONE").upper()
    session_key = (session or "UNKNOWN").upper()

    cooldown_seconds = 0
    reason = "NONE"

    if recovery != "NONE" or drawdown > 0.08 or volatility > 2.0 or loss_amount > 10.0:
        if volatility > 2.4:
            cooldown_seconds = 900
            reason = "VOLATILITY_SPIKE"
        elif recent_losses >= 2:
            cooldown_seconds = 600
            reason = "CONSECUTIVE_LOSSES"
        elif drawdown > 0.08:
            cooldown_seconds = 300
            reason = "DRAWDOWN_RECOVERY"
        elif loss_amount > 20.0:
            cooldown_seconds = 300
            reason = "NORMAL_STOP_LOSS"
        else:
            cooldown_seconds = 120
            reason = "SMALL_LOSS"

    if session_key in {"NEWS_VOLATILITY", "NEWS"} and cooldown_seconds > 0:
        cooldown_seconds = max(cooldown_seconds, 600)

    if cooldown_seconds > 0:
        cooldown_active = True
        cooldown_until = now_ts + cooldown_seconds
        reentry_ready = False
    else:
        cooldown_active = False
        cooldown_until = 0.0
        reentry_ready = True

    return {
        "cooldown_active": cooldown_active,
        "cooldown_seconds": int(cooldown_seconds),
        "cooldown_reason": reason,
        "cooldown_until": cooldown_until,
        "reentry_ready": reentry_ready,
        "analysis_only": cooldown_active,
        "reentry_mode": "SMART_REENTRY" if reentry_ready else "COOLDOWN",
    }


class RecoveryCooldownTracker:
    def __init__(self) -> None:
        self._cooldown_until = 0.0
        self._consecutive_losses = 0

    def record_outcome(
        self,
        outcome: str,
        loss_amount: float = 0.0,
        volatility: float = 0.0,
        drawdown: float = 0.0,
        session: str = "UNKNOWN",
        now: float | None = None,
    ) -> Dict[str, Any]:
        outcome = (outcome or "").upper()
        now_ts = float(now if now is not None else time.time())

        if outcome in {"LOSS", "LOSE", "LOST", "LOSS_TRADE"}:
            self._consecutive_losses += 1
            state = build_cooldown_state(
                recent_losses=self._consecutive_losses,
                drawdown=drawdown,
                volatility=volatility,
                loss_amount=loss_amount,
                session=session,
                recovery_state="ACTIVE",
                now=now_ts,
            )
            self._cooldown_until = state["cooldown_until"]
        else:
            self._consecutive_losses = max(0, self._consecutive_losses - 1)
            state = build_cooldown_state(
                recent_losses=self._consecutive_losses,
                drawdown=drawdown,
                volatility=volatility,
                loss_amount=loss_amount,
                session=session,
                recovery_state="NONE",
                now=now_ts,
            )
            self._cooldown_until = 0.0

        state["consecutive_losses"] = self._consecutive_losses
        return state

    def get_state(self, now: float | None = None) -> Dict[str, Any]:
        now_ts = float(now if now is not None else time.time())
        cooldown_active = now_ts < self._cooldown_until
        return {
            "cooldown_active": cooldown_active,
            "cooldown_until": self._cooldown_until,
            "cooldown_seconds": max(0, int(round(self._cooldown_until - now_ts))),
            "consecutive_losses": self._consecutive_losses,
            "analysis_only": cooldown_active,
            "reentry_mode": "SMART_REENTRY" if not cooldown_active else "COOLDOWN",
        }
