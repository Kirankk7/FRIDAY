"""
B — rich morning briefing. Assembles the day from agents that already exist:
friday (tasks/reminders/next event) + weather + news + crypto. Pure assembly,
each source graceful — a failing source is skipped, the brief still returns.
"""
import datetime


def _safe(fn, default=""):
    try:
        return fn()
    except Exception:
        return default


def build_briefing() -> dict:
    hour = datetime.datetime.now().hour
    tod = "Morning" if hour < 12 else "Afternoon" if hour < 17 else "Evening"
    parts = [f"{tod}, boss."]

    # Tasks / next event / reminders — friday
    def _friday_bits():
        from agents.friday import friday_agent as fa
        bits = []
        t = fa.list_tasks()
        if t.get("success") and t.get("data", {}).get("tasks"):
            n = len([x for x in t["data"]["tasks"] if not x.get("done")])
            if n:
                bits.append(f"{n} open task{'s' if n != 1 else ''}")
        ev = fa.next_event()
        if ev.get("success") and ev.get("message") and "no " not in ev["message"].lower():
            bits.append(ev["message"].rstrip("."))
        rem = fa.list_reminders()
        if rem.get("success") and rem.get("data", {}).get("reminders"):
            n = len([r for r in rem["data"]["reminders"] if not r.get("fired")])
            if n:
                bits.append(f"{n} reminder{'s' if n != 1 else ''} pending")
        return "  ".join(bits)
    day = _safe(_friday_bits)
    if day:
        parts.append(day + ".")

    # Weather
    def _wx():
        from core import weather
        w = weather.get_weather()
        return w.get("message", "") if w.get("success") else ""
    wx = _safe(_wx)
    if wx:
        parts.append(wx)

    # Crypto snapshot
    def _crypto():
        from agents.vision.vision_agent import vision_agent
        r = vision_agent.crypto_price("bitcoin,ethereum")
        return r.get("message", "") if r.get("success") else ""
    cx = _safe(_crypto)
    if cx:
        parts.append(cx + ".")

    # One news headline
    def _news():
        from agents.vision.vision_agent import vision_agent
        r = vision_agent.search_news("top news today")
        heads = (r.get("data", {}) or {}).get("headlines") or []
        return ("Top story: " + heads[0]) if heads else ""
    nx = _safe(_news)
    if nx:
        parts.append(nx if nx.endswith(".") else nx + ".")

    msg = "  ".join(p for p in parts if p)
    return {"success": True, "message": msg, "data": {"sections": len(parts)}}
