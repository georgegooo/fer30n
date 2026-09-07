import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class SecondaryShadowTests(unittest.TestCase):
    def test_evaluation_logs_without_execution_authority(self):
        import core.settings as settings
        from core.secondary_shadow import evaluate_secondary_shadow

        path = Path(tempfile.mkdtemp()) / "secondary.jsonl"
        old_path = settings.SECONDARY_SHADOW_LOG_PATH
        settings.SECONDARY_SHADOW_LOG_PATH = str(path)
        rates = [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5} for _ in range(20)]
        with patch("core.scalping_engine.get_scalping_signal", return_value="NONE"), \
             patch("core.swing_engine.get_swing_signal", return_value="NONE"):
            result = evaluate_secondary_shadow(
                symbol="XAUUSD", rates=rates, session="LONDON",
                market_regime="RANGING", confidence_pct=80,
            )
        settings.SECONDARY_SHADOW_LOG_PATH = old_path

        self.assertEqual(set(result), {"SCALP", "SWING", "MICRO"})
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["live_execution"] is False for row in rows))


if __name__ == "__main__":
    unittest.main()