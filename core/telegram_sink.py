"""
Optional Telegram delivery sink for JARVIS notifications.

Dormant until you set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env. Once set, every
notify.push() (security alerts, morning digest, reminders, CVE hits) is also delivered
to your Telegram chat — so JARVIS can reach you when you're away from the HUD.

Setup:
  1. Create a bot via @BotFather on Telegram -> get the bot token.
  2. Message your bot, then visit  https://api.telegram.org/bot<TOKEN>/getUpdates  to find
     your chat id.
  3. Put both in .env:  TELEGRAM_BOT_TOKEN=...   TELEGRAM_CHAT_ID=...
  4. Restart JARVIS — the bridge auto-enables (enable() is called at boot).
"""
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

_KIND_TAG = {"security": "[SECURITY]", "digest": "[Digest]",
             "reminder": "[Reminder]", "info": "[JARVIS]"}


def _send(item: dict) -> None:
    """notify sink — fire-and-forget a push to Telegram. Never raises."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    try:
        import requests
        tag = _KIND_TAG.get(item.get("kind", "info"), "[JARVIS]")
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"{tag} {item.get('text', '')}"},
            timeout=8,
        )
    except Exception as e:
        print(f"[telegram] send failed: {e}")


def enable() -> bool:
    """Register the Telegram sink if creds are configured. No-op (returns False) otherwise."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        from core import notify
        notify.register_sink(_send)
        print("[telegram] bridge enabled")
        return True
    return False
