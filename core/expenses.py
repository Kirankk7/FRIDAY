"""
H — expense / spending log. Local, no bank integration. data/expenses.json (gitignored).
"""
import os
import json
import datetime

_PATH = os.path.join("data", "expenses.json")


def _load() -> list:
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d.get("items", []) if isinstance(d, dict) else []
    except Exception:
        return []


def _save(items: list) -> None:
    os.makedirs("data", exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump({"items": items}, f, indent=2)


def add_expense(amount, category: str = "misc", note: str = "") -> dict:
    try:
        amount = float(amount)
    except Exception:
        return {"success": False, "message": "Amount must be a number, boss."}
    items = _load()
    items.append({"amount": amount, "category": (category or "misc").strip().lower(),
                  "note": (note or "").strip(), "ts": datetime.datetime.now().isoformat()})
    _save(items)
    return {"success": True, "message": f"Logged ${amount:,.2f} on {category or 'misc'}."}


def _in_window(ts: str, window: str) -> bool:
    if window in ("all", "", None):
        return True
    try:
        d = datetime.datetime.fromisoformat(ts)
    except Exception:
        return False
    now = datetime.datetime.now()
    if window == "today":
        return d.date() == now.date()
    if window == "week":
        return d >= now - datetime.timedelta(days=7)
    if window == "month":
        return d >= now - datetime.timedelta(days=30)
    return True


def report(window: str = "week") -> dict:
    items = [i for i in _load() if _in_window(i.get("ts", ""), window)]
    if not items:
        return {"success": True, "message": f"No expenses logged for {window}.",
                "data": {"total": 0.0, "count": 0}}
    total = sum(i.get("amount", 0) for i in items)
    return {"success": True, "message": f"Spent ${total:,.2f} across {len(items)} item(s) ({window}).",
            "data": {"total": total, "count": len(items)}}


def by_category(window: str = "all") -> dict:
    items = [i for i in _load() if _in_window(i.get("ts", ""), window)]
    if not items:
        return {"success": True, "message": f"No expenses logged for {window}.", "data": {}}
    cats = {}
    for i in items:
        cats[i.get("category", "misc")] = cats.get(i.get("category", "misc"), 0.0) + i.get("amount", 0)
    ranked = sorted(cats.items(), key=lambda kv: kv[1], reverse=True)
    msg = " · ".join(f"{c}: ${v:,.2f}" for c, v in ranked)
    return {"success": True, "message": f"Spending by category ({window}): {msg}", "data": cats}
