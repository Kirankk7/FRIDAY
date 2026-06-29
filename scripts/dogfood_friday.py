#!/usr/bin/env python
"""Dogfood the sibling friday-recon CLI — safe-verb smoke + suite.

Mirrors what `scripts/coverage.py` does for JARVIS: enumerates the friday-recon
CLI's read-only verbs, runs each, checks exit code + sane output (no stacktrace,
no ANSI leak). Plus a `pytest` run on its own suite. Skips heavy verbs (recon,
bugbounty, scan, idor) — those run real scans against targets.

Run:  python scripts/dogfood_friday.py
"""
import os, sys, time, subprocess, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.abspath(os.path.join(ROOT, "..", "friday-recon"))
LOG = os.path.join(ROOT, "DOGFOOD_LOG.md")
PY = sys.executable
ENV = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CRASH = re.compile(r"Traceback \(most recent call last\)", re.I)

# Safe CLI verbs to smoke (read-only, no network/scan)
SAFE_VERBS = [
    ["--help"], ["sessions"], ["targets"], ["scope"], ["wordlist"],
]


def run_cli(args, timeout=20):
    cmd = [PY, "cli.py"] + args
    try:
        r = subprocess.run(cmd, cwd=REPO, env=ENV, capture_output=True,
                           text=True, timeout=timeout, encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0 and "usage:" not in out.lower():
            return "FAIL", f"exit {r.returncode}: {out.splitlines()[-1][:80] if out else 'no output'}"
        if _CRASH.search(out):
            return "FAIL", "stacktrace leaked"
        if _ANSI.search(out):
            return "FAIL", "ANSI escape leaked"
        return "PASS", f"{len(out)}b ok"
    except subprocess.TimeoutExpired:
        return "FAIL", f"TIMEOUT >{timeout}s"
    except Exception as e:
        return "FAIL", f"crash: {str(e)[:80]}"


def run_pytest():
    try:
        r = subprocess.run([PY, "-m", "pytest", "-q", "tests/"], cwd=REPO, env=ENV,
                           capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "")
        tail = next((ln for ln in reversed(out.splitlines())
                     if "passed" in ln or "failed" in ln or "error" in ln), "(no summary)")
        return ("PASS" if r.returncode == 0 else "FAIL", tail[:100])
    except FileNotFoundError:
        return "SKIP", "pytest not installed"
    except subprocess.TimeoutExpired:
        return "FAIL", "TIMEOUT >180s"
    except Exception as e:
        return "FAIL", f"crash: {str(e)[:80]}"


def main():
    if not os.path.isfile(os.path.join(REPO, "cli.py")):
        print(f"friday-recon not found at {REPO} — skip.")
        sys.exit(0)
    rows = []
    for args in SAFE_VERBS:
        status, detail = run_cli(args)
        rows.append((f"cli.py {' '.join(args)}", status, detail))
    pst, pdt = run_pytest()
    rows.append(("pytest tests/", pst, pdt))

    fails = sum(1 for _, s, _ in rows if s == "FAIL")
    print(f"\n=== friday-recon dogfood ({time.strftime('%Y-%m-%d %H:%M')}) ===")
    for name, status, detail in rows:
        print(f"  [{status:4}] {name:40} — {detail}")
    print(f"\n{sum(1 for _,s,_ in rows if s=='PASS')}/{len(rows)} pass · {fails} fail")

    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"\n### {time.strftime('%Y-%m-%d %H:%M')} — dogfood_friday\n")
            for name, status, detail in rows:
                f.write(f"- [{status}] {name} — {detail}\n")
    except Exception:
        pass
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
