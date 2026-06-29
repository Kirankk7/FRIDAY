#!/usr/bin/env python
"""Dogfood meta-runner — chain coverage + probe-lab + chat-battery into one rollup.

Runs the three Tier-0 batteries in sequence and writes a single pass/fail
summary to DOGFOOD_LOG.md. Skips any that need a missing prereq (probe_lab on
:7000 for the security bench; the chat battery runs --inproc so no server
needed). Exits non-zero if any sub-battery fails.

Run:  python scripts/dogfood_all.py [--no-chat] [--no-probe] [--no-coverage]
"""
import os, sys, time, subprocess, argparse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "DOGFOOD_LOG.md")
PY = sys.executable
ENV = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", JARVIS_CI="1")


def _probe_lab_up():
    try:
        urllib.request.urlopen("http://127.0.0.1:7000/", timeout=3)
        return True
    except Exception:
        return False


def run(label, cmd, skip_reason=None, timeout=600):
    if skip_reason:
        return (label, "SKIP", 0, skip_reason)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=ROOT, env=ENV, capture_output=True,
                           text=True, timeout=timeout, encoding="utf-8", errors="replace")
        dt = time.time() - t0
        tail = (r.stdout or "").strip().splitlines()
        summary = next((ln for ln in reversed(tail) if any(k in ln.lower()
                       for k in ("pass", "fail", "broken", "working", "results:"))), "(no summary)")
        return (label, "PASS" if r.returncode == 0 else "FAIL", dt, summary[:140])
    except subprocess.TimeoutExpired:
        return (label, "FAIL", time.time() - t0, f"TIMEOUT >{timeout}s")
    except Exception as e:
        return (label, "FAIL", time.time() - t0, f"crash: {str(e)[:80]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-chat", action="store_true")
    ap.add_argument("--no-probe", action="store_true")
    ap.add_argument("--no-coverage", action="store_true")
    args = ap.parse_args()

    results = []
    if not args.no_coverage:
        results.append(run("coverage  (all-agent registry smoke)",
                           [PY, "scripts/coverage.py"]))
    if not args.no_probe:
        skip = None if _probe_lab_up() else "probe_lab not on :7000 (run `python labs/probe_lab/app.py`)"
        results.append(run("probe-lab (ultron TP/FP bench)",
                           [PY, "scripts/dogfood.py"], skip_reason=skip, timeout=300))
    if not args.no_chat:
        results.append(run("chat-battery (--inproc, 281 inputs)",
                           [PY, "scripts/chat_battery.py", "--inproc", "--timeout", "40", "--quiet"],
                           timeout=1800))

    fails = sum(1 for _, st, *_ in results if st == "FAIL")
    print(f"\n=== Dogfood rollup ({time.strftime('%Y-%m-%d %H:%M')}) ===")
    for label, status, dt, summary in results:
        print(f"  [{status:4}] {label:40} {dt:5.0f}s  {summary}")
    print(f"\n{len(results)-fails}/{len(results)} battery passed · {fails} failed")

    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"\n### {time.strftime('%Y-%m-%d %H:%M')} — dogfood_all rollup\n")
            for label, status, dt, summary in results:
                f.write(f"- [{status}] {label} ({dt:.0f}s) — {summary}\n")
    except Exception:
        pass
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
