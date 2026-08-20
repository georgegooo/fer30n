import os
import requests

try:
    from dotenv import load_dotenv
except ImportError:  # dependency is optional at runtime if env vars are already set
    def load_dotenv(*args, **kwargs):
        return False

# =========================================
# LOAD ENV
# =========================================

load_dotenv("config.env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_TOKEN", "")).strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
BASE_URL = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""


def _telegram_ready():
    return bool(TOKEN and CHAT_ID and BASE_URL)


# =========================================
# SEND MESSAGE
# =========================================

def send_telegram_message(message):
    if not _telegram_ready():
        print("ℹ️ Telegram skipped: credentials not configured")
        return False

    try:
        url = f"{BASE_URL}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": str(message)}
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as error:
        print(f"❌ Telegram Error: {error}")
        return False


# =========================================
# GET LAST COMMAND
# =========================================

def get_last_command(last_update_id):
    if not _telegram_ready():
        return None, last_update_id

    try:
        params = {"timeout": 5}
        if last_update_id is not None:
            params["offset"] = last_update_id

        response = requests.get(
            f"{BASE_URL}/getUpdates",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, dict) or not data.get("ok"):
            return None, last_update_id

        results = data.get("result", [])
        if not results:
            return None, last_update_id

        last = results[-1]
        update_id = last.get("update_id", last_update_id)
        message = last.get("message", {})
        text = message.get("text")
        return text, update_id + 1

    except Exception as error:
        print(f"❌ Telegram Polling Error: {error}")
        return None, last_update_id


# V5.1 Command handlers (تُستدعى من main.py)
# /choch   → get_full_structure_analysis
# /liqmap  → build_liquidity_map
# /weights → get_adaptive_weights
# /adapt   → run_adaptive_weighting(force=True)
