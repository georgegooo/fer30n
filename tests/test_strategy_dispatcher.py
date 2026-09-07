from runtime.strategy_dispatcher import dispatch_secondary_strategies


def test_micro_can_run_independently_from_secondary_strategies():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return {"opened": False, "reason": "NO_SIGNAL"}

    runners = {"SCALP": runner, "SWING": runner, "MICRO": runner}
    result = dispatch_secondary_strategies(
        {"session": "OFF_HOURS", "market_regime": "TRENDING"},
        allow_execution=True,
        enabled_strategies={"MICRO": True, "SCALP": False, "SWING": False},
        runners=runners,
    )

    assert len(calls) == 1
    assert result["MICRO"]["reason"] == "NO_SIGNAL"
    assert result["SCALP"]["reason"] == "STRATEGY_LIVE_DISABLED"
    assert result["SWING"]["reason"] == "STRATEGY_LIVE_DISABLED"


def test_authority_closed_disables_all_secondary_runners():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        return {"opened": True}

    runners = {"SCALP": runner, "SWING": runner, "MICRO": runner}
    result = dispatch_secondary_strategies(
        {"session": "LONDON", "market_regime": "RANGING"},
        allow_execution=False,
        enabled_strategies={"MICRO": False, "SCALP": False, "SWING": False},
        runners=runners,
    )

    assert calls == []
    assert all(value["reason"] == "CANONICAL_AUTHORITY_BLOCK" for value in result.values())