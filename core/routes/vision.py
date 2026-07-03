"""Router group — vision live-info (currency / translate / flight / crypto price).

Extracted VERBATIM from route_single_intent (Phase 41 block + broadened vision
fallbacks). Behaviour-identical: called in the exact chain position it used to occupy,
so order vs the surrounding groups is preserved. Uses only text (lowercased).
Returns a decision dict, or None to fall through.

Refactor discipline: move only — no logic changes.
"""
import re


def try_route(text: str, text_raw: str):
    _CCY = {"dollar": "USD", "dollars": "USD", "usd": "USD", "euro": "EUR", "euros": "EUR",
            "eur": "EUR", "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "rupee": "INR",
            "rupees": "INR", "inr": "INR", "yen": "JPY", "jpy": "JPY", "yuan": "CNY"}

    # Currency conversion: "convert 500 usd to eur" / "100 dollars in euros"
    _m = re.match(
        r"(?:convert\s+)?(\d[\d,]*\.?\d*)\s*([a-z]{3}|dollars?|euros?|pounds?|rupees?|yen|yuan)\s+"
        r"(?:to|in|into)\s+([a-z]{3}|dollars?|euros?|pounds?|rupees?|yen|yuan)\b",
        text, re.IGNORECASE
    )
    if _m:
        amt = float(_m.group(1).replace(",", ""))
        frm = _CCY.get(_m.group(2).lower(), _m.group(2).upper())
        to = _CCY.get(_m.group(3).lower(), _m.group(3).upper())
        return {"tool": "vision", "action": "currency_convert",
                "parameters": {"amount": amt, "from": frm, "to": to}, "confidence": 0.97}

    # Translate: "translate X to french" / "how do you say X in spanish"
    _m = re.match(r"(?:translate|how do (?:you|i) say)\s+(.+?)\s+(?:to|in|into)\s+(\w+)\??$", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "translate",
                "parameters": {"text": _m.group(1).strip().strip("'\""), "target": _m.group(2).strip()}, "confidence": 0.96}
    # "translate to french: X"
    _m = re.match(r"translate\s+(?:to\s+)?(\w+)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "translate",
                "parameters": {"text": _m.group(2).strip(), "target": _m.group(1).strip()}, "confidence": 0.95}

    # Flight tracking: "track flight EK202" / "flight status BA117"
    _m = re.match(r"(?:track flight|flight status(?: of)?|where is flight|flight)\s+([a-z]{2}\s?\d{1,4}[a-z]?)\b", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "track_flight",
                "parameters": {"flight": _m.group(1).strip()}, "confidence": 0.96}

    # Crypto price: "bitcoin price" / "price of ethereum" / "how much is btc"
    _coin_re = r"(bitcoin|btc|ethereum|eth|solana|sol|dogecoin|doge|ripple|xrp|cardano|ada|bnb|binancecoin|litecoin|ltc|polkadot|dot|chainlink|link|avalanche|avax|matic)"
    _m = re.match(rf"{_coin_re}\s+price$", text, re.IGNORECASE)
    if not _m:
        _m = re.match(rf"(?:price of|how much is|what(?:'s| is) (?:the )?price of)\s+{_coin_re}\b", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "crypto_price",
                "parameters": {"coins": _m.group(1)}, "confidence": 0.96}
    if text in ("crypto prices", "top crypto", "crypto market", "coin prices"):
        return {"tool": "vision", "action": "crypto_price",
                "parameters": {"coins": "bitcoin,ethereum,solana,bnb,ripple"}, "confidence": 0.95}

    # Broadened vision fallbacks — clear commands the strict patterns above miss, so they route
    # deterministically instead of falling to the (unreliable, local-model) LLM router.
    if re.search(rf"\b{_coin_re}\b.{{0,25}}\bprice\b|\bprice\b.{{0,25}}\b{_coin_re}\b|"
                 rf"how much is\s+(?:the\s+)?{_coin_re}\b|{_coin_re}\s+(?:is\s+)?worth", text, re.IGNORECASE):
        _cm = re.search(_coin_re, text, re.IGNORECASE)
        return {"tool": "vision", "action": "crypto_price",
                "parameters": {"coins": _cm.group(1)}, "confidence": 0.93}
    _m = re.search(r"(\d[\d,]*\.?\d*)\s*([a-z]{3}|dollars?|euros?|pounds?|rupees?|yen|yuan)\s+"
                   r"(?:to|in|into)\s+([a-z]{3}|dollars?|euros?|pounds?|rupees?|yen|yuan)\b", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "currency_convert",
                "parameters": {"amount": float(_m.group(1).replace(",", "")),
                               "from": _CCY.get(_m.group(2).lower(), _m.group(2).upper()),
                               "to": _CCY.get(_m.group(3).lower(), _m.group(3).upper())}, "confidence": 0.93}
    _m = re.search(r"what does\s+(.+?)\s+mean(?:\s+in\s+(\w+))?", text, re.IGNORECASE)
    if _m:
        return {"tool": "vision", "action": "translate",
                "parameters": {"text": _m.group(1).strip().strip("'\""),
                               "target": (_m.group(2) or "english").strip()}, "confidence": 0.92}

    return None
