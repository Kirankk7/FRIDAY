"""
Phase 63 — per-target memory for Ultron.

Persistent profile per host/target across hunts: scans run, findings, discovered
endpoints, and freeform notes. So Ultron *remembers* a target between sessions
("what did we find on acme.com last time?"). Local JSON, no deps.
"""

import os
import json
import datetime
import threading

_FILE = os.path.join("data", "target_profiles.json")
_lock = threading.Lock()


def _norm(host: str) -> str:
    import re
    h = (host or "").strip().lower()
    h = re.sub(r"^https?://", "", h).rstrip("/")
    return h.split("/")[0]


def _load() -> dict:
    try:
        if os.path.exists(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save(data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_FILE), exist_ok=True)
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[target_profiles] save error: {e}")


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _get(data: dict, host: str) -> dict:
    p = data.setdefault(host, {})
    p.setdefault("host", host)
    p.setdefault("first_seen", _now())
    p["last_seen"] = _now()
    for k in ("scans", "findings", "endpoints", "notes"):
        p.setdefault(k, [])
    return p


def record_scan(host: str, kind: str, summary: str) -> None:
    host = _norm(host)
    if not host:
        return
    with _lock:
        data = _load()
        p = _get(data, host)
        p["scans"].append({"kind": kind, "summary": (summary or "")[:300], "ts": _now()})
        p["scans"] = p["scans"][-50:]
        _save(data)


def record_findings(host: str, findings: list) -> None:
    """findings = list of dicts (Ultron finding shape) or strings."""
    host = _norm(host)
    if not host or not findings:
        return
    with _lock:
        data = _load()
        p = _get(data, host)
        for f in findings:
            if isinstance(f, dict):
                p["findings"].append({"template": f.get("template", ""),
                                      "severity": f.get("severity", ""),
                                      "url": f.get("url", ""), "ts": _now()})
            else:
                p["findings"].append({"template": str(f)[:120], "ts": _now()})
        # dedupe by (template,url), keep newest
        seen, dedup = set(), []
        for f in reversed(p["findings"]):
            key = (f.get("template", ""), f.get("url", ""))
            if key not in seen:
                seen.add(key); dedup.append(f)
        p["findings"] = list(reversed(dedup))[-100:]
        _save(data)


def record_endpoints(host: str, endpoints: list) -> None:
    host = _norm(host)
    if not host or not endpoints:
        return
    with _lock:
        data = _load()
        p = _get(data, host)
        existing = set(p["endpoints"])
        for e in endpoints:
            if e and e not in existing:
                p["endpoints"].append(e); existing.add(e)
        p["endpoints"] = p["endpoints"][-500:]
        _save(data)


def add_note(host: str, note: str) -> dict:
    host = _norm(host)
    if not host or not note.strip():
        return {"success": False, "message": "Need a host and a note, boss."}
    with _lock:
        data = _load()
        p = _get(data, host)
        p["notes"].append({"note": note.strip(), "ts": _now()})
        _save(data)
    return {"success": True, "message": f"Noted on {host}."}


def summary(host: str) -> dict:
    host = _norm(host)
    data = _load()
    p = data.get(host)
    if not p:
        return {"success": True, "message": f"No profile for {host} yet — nothing scanned.",
                "data": {}}
    crit = sum(1 for f in p["findings"] if f.get("severity") == "critical")
    high = sum(1 for f in p["findings"] if f.get("severity") == "high")
    lines = [
        f"Target profile: {host}",
        f"First seen {p['first_seen'][:10]}, last {p['last_seen'][:10]}.",
        f"{len(p['scans'])} scan(s), {len(p['findings'])} finding(s) ({crit} critical, {high} high), "
        f"{len(p['endpoints'])} endpoint(s).",
    ]
    if p["scans"]:
        lines.append("Recent scans: " + ", ".join(s["kind"] for s in p["scans"][-5:]))
    if p["notes"]:
        lines.append("Notes: " + " | ".join(n["note"] for n in p["notes"][-3:]))
    return {"success": True, "message": "\n".join(lines), "data": p}


def list_targets() -> dict:
    data = _load()
    if not data:
        return {"success": True, "message": "No targets profiled yet, boss.", "data": {"targets": []}}
    names = sorted(data.keys())
    return {"success": True, "message": "Profiled targets: " + ", ".join(names),
            "data": {"targets": names}}
