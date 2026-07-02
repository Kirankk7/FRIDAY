"""
I (backend) — findings feed for the HUD. Reads the saved bug-bounty reports and
surfaces recent gate-passed findings (target / count / top severity / when).
Read-only, graceful when no reports exist.
"""
import os
import re
import glob
import datetime


def _reports_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "Desktop", "Ultron Reports")


def recent(limit: int = 20) -> list:
    base = _reports_dir()
    try:
        files = glob.glob(os.path.join(base, "*", "bugbounty_*.md"))
    except Exception:
        return []
    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    out = []
    for f in files[:max(1, limit)]:
        try:
            txt = open(f, encoding="utf-8").read()
        except Exception:
            continue
        target = os.path.basename(os.path.dirname(f)).replace("_", ".")
        m = re.search(r"Reportable findings:\s*\*\*(\d+)\*\*(.*)", txt)
        count = int(m.group(1)) if m else 0
        sev = re.search(r"P[1-5]", m.group(2)) if m else None
        sev = sev or re.search(r"P[1-5]\s*\((?:Critical|High|Medium)\)", txt)
        out.append({
            "target": target,
            "count": count,
            "severity": sev.group(0) if sev else "-",
            "when": datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M"),
            "file": f,
        })
    return out
