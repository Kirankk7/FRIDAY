"""
E — crypto portfolio watchlist. Local holdings store valued live via vision.crypto_price
(CoinGecko, no key). Plumbing, no model. data/portfolio.json (gitignored).
"""
import os
import json

_PATH = os.path.join("data", "portfolio.json")


def _load() -> dict:
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {"holdings": {}}
    except Exception:
        return {"holdings": {}}


def _save(d: dict) -> None:
    os.makedirs("data", exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)


def holdings() -> dict:
    return _load().get("holdings", {})


def add_holding(amount: float, coin: str) -> dict:
    coin = (coin or "").strip().lower()
    try:
        amount = float(amount)
    except Exception:
        return {"success": False, "message": "Amount must be a number, boss."}
    if not coin:
        return {"success": False, "message": "Which coin, boss?"}
    d = _load()
    d.setdefault("holdings", {})
    d["holdings"][coin] = d["holdings"].get(coin, 0.0) + amount
    _save(d)
    return {"success": True, "message": f"Added {amount:g} {coin.upper()}. Holding {d['holdings'][coin]:g} now."}


def remove_holding(coin: str) -> dict:
    coin = (coin or "").strip().lower()
    d = _load()
    if coin in d.get("holdings", {}):
        d["holdings"].pop(coin)
        _save(d)
        return {"success": True, "message": f"Removed {coin.upper()} from the portfolio."}
    return {"success": False, "message": f"No {coin.upper()} in the portfolio."}


def clear() -> dict:
    _save({"holdings": {}})
    return {"success": True, "message": "Portfolio cleared."}


def value(price_fn=None) -> dict:
    """Value every holding live. price_fn(coin)->usd override for tests (else vision.crypto_price)."""
    h = holdings()
    if not h:
        return {"success": True, "message": "Portfolio's empty — add one: 'add holding 0.5 btc'.",
                "data": {"total": 0.0, "lines": []}}

    def _price(coin):
        if price_fn:
            return price_fn(coin)
        try:
            from agents.vision.vision_agent import vision_agent
            r = vision_agent.crypto_price(coin)
            data = r.get("data", {}) if r.get("success") else {}
            if data:
                return list(data.values())[0].get("usd")
        except Exception:
            pass
        return None

    lines, total, priced = [], 0.0, False
    for coin, amt in h.items():
        p = _price(coin)
        if isinstance(p, (int, float)):
            v = p * amt
            total += v
            priced = True
            lines.append(f"{coin.upper()}: {amt:g} × ${p:,.2f} = ${v:,.2f}")
        else:
            lines.append(f"{coin.upper()}: {amt:g} (price unavailable)")
    msg = " · ".join(lines)
    if priced:
        msg += f"  ->  Total: ${total:,.2f}"
    return {"success": True, "message": msg, "data": {"total": total, "lines": lines}}
