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


# ── C — inbound command & control (two-way) ─────────────────────────────────
# A getUpdates poller lets you DRIVE JARVIS from your phone. Only TELEGRAM_CHAT_ID
# may issue commands; any other chat is ignored. Long ops run on the poll thread's
# own turn, never blocking the notify path.

def _authorized_text(update: dict):
    """Extract the command text from a getUpdates result item IF it's from the
    authorized chat. Returns the text, or None (wrong chat / no message). Pure —
    unit-testable without network."""
    msg = (update or {}).get("message") or (update or {}).get("edited_message") or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    text = (msg.get("text") or "").strip()
    if not text:
        return None
    if str(TELEGRAM_CHAT_ID) and chat_id != str(TELEGRAM_CHAT_ID):
        return None      # not you — ignore
    return text


def _reply(text: str) -> None:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    try:
        import requests
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": text[:3500]}, timeout=8)
    except Exception as e:
        print(f"[telegram] reply failed: {e}")


def _handle(text: str) -> str:
    """Run an inbound command through the brain, return the reply text."""
    # strip a leading slash-command style ("/task buy milk" -> "task buy milk")
    if text.startswith("/"):
        text = text[1:]
    try:
        from core.brain import process_input
        return process_input(text) or "Done, boss."
    except Exception as e:
        return f"Hit a snag: {str(e)[:80]}"


def _poll_loop():
    import time
    import requests
    offset = None
    print("[telegram] inbound poller started")
    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset
            r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                             params=params, timeout=40)
            for upd in (r.json() or {}).get("result", []):
                offset = upd["update_id"] + 1
                cmd = _authorized_text(upd)
                if cmd:
                    _reply(_handle(cmd))
        except Exception as e:
            print(f"[telegram] poll error: {str(e)[:80]}")
            time.sleep(5)


def start_polling() -> bool:
    """Start the inbound command poller on a daemon thread (only if creds set)."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    import threading
    threading.Thread(target=_poll_loop, daemon=True).start()
    return True
