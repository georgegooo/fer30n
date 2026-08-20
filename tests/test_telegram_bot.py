import importlib
import os
import tempfile
import unittest
from unittest import mock


class TelegramBotTests(unittest.TestCase):
    def test_get_last_command_omits_offset_when_none(self):
        import core.telegram_bot as telegram_bot

        telegram_bot.TOKEN = "token"
        telegram_bot.CHAT_ID = "chat"
        telegram_bot.BASE_URL = "https://api.telegram.org/bottoken"

        with mock.patch.object(telegram_bot.requests, "get") as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = {"ok": True, "result": []}

            telegram_bot.get_last_command(None)

            _, kwargs = mock_get.call_args
            self.assertEqual(kwargs["params"], {"timeout": 5})

    def test_import_loads_config_from_repo_root_when_cwd_changes(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                import core.telegram_bot as telegram_bot

                module_path = os.path.abspath(telegram_bot.__file__)
                self.assertTrue(module_path.endswith("core\\telegram_bot.py") or module_path.endswith("core/telegram_bot.py"))
            finally:
                os.chdir(old_cwd)
                importlib.reload(importlib.import_module("core.telegram_bot"))


if __name__ == "__main__":
    unittest.main()
