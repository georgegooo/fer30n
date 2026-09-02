import main


def test_trigger_parallel_strategy_runners_calls_all_live_runners(monkeypatch):
    calls = []

    def fake_scalp(**kwargs):
        calls.append(("SCALP", kwargs))
        return {"opened": False, "reason": "SCALP_OK"}

    def fake_swing(**kwargs):
        calls.append(("SWING", kwargs))
        return {"opened": False, "reason": "SWING_OK"}

    def fake_micro(**kwargs):
        calls.append(("MICRO", kwargs))
        return {"opened": False, "reason": "MICRO_OK"}

    monkeypatch.setattr(main, "run_scalp_cycle", fake_scalp)
    monkeypatch.setattr(main, "run_swing_cycle", fake_swing)
    monkeypatch.setattr(main, "run_micro_cycle", fake_micro)

    snapshot = {
        "ready": True,
        "session": "LONDON",
        "market_regime": "TRENDING",
        "confidence": {"pct": 72},
    }

    result = main.trigger_parallel_strategy_runners(snapshot)

    assert set(result.keys()) == {"SCALP", "SWING", "MICRO"}
    assert {name for name, _ in calls} == {"SCALP", "SWING", "MICRO"}
    assert result["SCALP"]["reason"] == "SCALP_OK"
    assert result["MICRO"]["reason"] == "MICRO_OK"
    assert calls[0][1]["session"] == "LONDON"


def test_trigger_parallel_strategy_runners_can_be_blocked_by_canonical_gate(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "run_scalp_cycle", lambda **kwargs: calls.append("SCALP"))
    monkeypatch.setattr(main, "run_swing_cycle", lambda **kwargs: calls.append("SWING"))
    monkeypatch.setattr(main, "run_micro_cycle", lambda **kwargs: calls.append("MICRO"))

    result = main.trigger_parallel_strategy_runners({}, allow_execution=False)

    assert calls == []
    assert all(item["reason"] == "CANONICAL_AUTHORITY_BLOCK" for item in result.values())
