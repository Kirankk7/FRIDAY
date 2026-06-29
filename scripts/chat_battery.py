#!/usr/bin/env python
"""
Chat battery (Tier 0, front-door): drive the REAL chat path with a maintained corpus and
assert it NEVER crashes/hangs/leaks, and that logic inputs route to the right agent.

Two dimensions per corpus line (data/chat_corpus.jsonl, {input, kind, expect}):
  kind=robust  -> adversarial/edge input; PASS = no crash, no hang, no stacktrace-to-user,
                  no ANSI leak, response length-governed.
  kind=logic   -> real task; PASS = routed to expect.agent (and not expect.not_agent).
                  Answer prose is model-bound, so only ROUTE is hard-scored; content is a note.

Modes:
  live (default) -> GET <base>/chat_stream?message=... , parse SSE (chunk/agent/done). Faithful;
                    gives true hang detection via wall-clock deadline. Needs the server running.
  --inproc       -> call core.brain.process_input_stream directly (no server). Catches crashes
                    offline (CI); hang detection via thread-join timeout.

Run:   python app.py                       # start server (live mode)
       python scripts/chat_battery.py      # or: --inproc  (no server, CI)
Exit:  non-zero if ANY robust crash/hang/leak or ANY logic route mismatch.
"""
import os, sys, json, time, argparse, re, threading
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "data", "chat_corpus.jsonl")
LOG = os.path.join(ROOT, "DOGFOOD_LOG.md")

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_TAGLEAK = re.compile(r"\[(AGENT|ULTRON|ATHENA|FRIDAY|SYSTEM)\b")
_CRASH = re.compile(r"Traceback \(most recent call last\)|Internal Server Error|500 Internal", re.I)
_WALL = "spam dummy filler text. " * 2200          # ~50k chars


def load_corpus():
    rows = []
    with open(CORPUS, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln, strict=False))   # corpus holds real ctrl chars on purpose
    return rows


def _expand(inp):
    return _WALL if inp == "__WALL__" else inp


def drive_live(base, msg, timeout):
    """Returns (answer, agent, status) where status in ok|hang|crash."""
    import requests
    url = f"{base}/chat_stream?message={quote(msg)}"
    chunks, agent, done = [], "", False
    deadline = time.time() + timeout
    try:
        r = requests.get(url, stream=True, timeout=(5, timeout))
        if r.status_code == 414:                  # URI too long = graceful reject (not a crash)
            return "HTTP 414 (URI too long — graceful)", "", "ok"
        if r.status_code != 200:
            return f"HTTP {r.status_code}", "", "crash"
        for raw in r.iter_lines(decode_unicode=True):
            if time.time() > deadline:
                return "".join(chunks), agent, "hang"
            if not raw or not raw.startswith("data: "):
                continue
            try:
                ev = json.loads(raw[6:])
            except Exception:
                continue
            t = ev.get("type")
            if t == "chunk":
                chunks.append(ev.get("value", ""))
            elif t == "agent":
                agent = ev.get("value", "") or agent
            elif t == "done":
                done = True
                break
        return "".join(chunks), agent, ("ok" if done else "hang")
    except requests.exceptions.ReadTimeout:
        return "".join(chunks), agent, "hang"
    except Exception as e:
        return f"{type(e).__name__}: {e}", "", "crash"


def drive_inproc(msg, timeout):
    from core import brain, state
    box = {"chunks": [], "err": None, "agent": ""}

    def run():
        try:
            for c in brain.process_input_stream(msg):
                box["chunks"].append(c)
            box["agent"] = state.get_last_agent()
        except BaseException as e:                 # a crash = the bug we hunt
            box["err"] = f"{type(e).__name__}: {e}"

    th = threading.Thread(target=run, daemon=True)
    th.start(); th.join(timeout)
    if th.is_alive():
        return "".join(box["chunks"]), box["agent"], "hang"
    if box["err"]:
        return box["err"], "", "crash"
    return "".join(box["chunks"]), box["agent"], "ok"


def classify(row, answer, agent, status):
    """Returns (verdict, reason). verdict in PASS|FAIL|WARN."""
    if status == "crash":
        return "FAIL", f"CRASH: {answer[:80]}"
    if status == "hang":
        return "FAIL", "HANG (no 'done' before timeout)"
    if _CRASH.search(answer):
        return "FAIL", "stacktrace/500 leaked to user"
    if _ANSI.search(answer):
        return "FAIL", "ANSI escape leaked"
    if _TAGLEAK.search(answer):
        return "FAIL", "internal [AGENT] tag leaked"
    exp = row.get("expect") or {}
    cap = exp.get("max_chars", 12000)
    if len(answer) > cap:
        return "FAIL", f"ungoverned length {len(answer)} > {cap}"
    # route check whenever an expectation is set (any kind)
    if exp.get("agent") and agent != exp["agent"]:
        return "FAIL", f"misroute: got '{agent}', want '{exp['agent']}'"
    if exp.get("not_agent") and agent == exp["not_agent"]:
        return "FAIL", f"wrong-fire: routed to '{agent}' (should not)"
    return "PASS", agent or "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5000")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--inproc", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--heavy", action="store_true", help="include heavy (network/scan) inputs")
    ap.add_argument("--record", default="", help="record run_id; dumps replies to "
                    "data/chat_replies/<run_id>.jsonl for review by chat_review.py")
    args = ap.parse_args()

    rows = load_corpus()
    if not args.heavy:
        rows = [r for r in rows if not r.get("heavy")]

    rec_path = None
    if args.record:
        rec_dir = os.path.join(ROOT, "data", "chat_replies")
        os.makedirs(rec_dir, exist_ok=True)
        rec_path = os.path.join(rec_dir, f"{args.record}.jsonl")
        open(rec_path, "w", encoding="utf-8").close()       # truncate
    if not args.inproc:
        import requests
        try:
            requests.get(args.base + "/", timeout=4)
        except Exception:
            print(f"server not reachable at {args.base} — run `python app.py` or use --inproc")
            sys.exit(2)

    results, fails = [], 0
    for row in rows:
        msg = _expand(row["input"])
        t0 = time.time()
        if args.inproc:
            answer, agent, status = drive_inproc(msg, args.timeout)
        else:
            answer, agent, status = drive_live(args.base, msg, args.timeout)
        latency_ms = int((time.time() - t0) * 1000)
        verdict, reason = classify(row, answer, agent, status)
        if verdict == "FAIL":
            fails += 1
        results.append((verdict, row["kind"], row["input"][:38], reason))
        if rec_path:
            with open(rec_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "input": row["input"], "kind": row["kind"], "agent": agent,
                    "reply": answer, "status": status, "verdict": verdict,
                    "latency_ms": latency_ms, "expect": row.get("expect", {}),
                }, ensure_ascii=False) + "\n")
        if not args.quiet:
            mark = {"PASS": "OK ", "FAIL": "XX ", "WARN": "?? "}[verdict]
            print(f"{mark} [{row['kind']:6}] {row['input'][:38]:38} -> {reason}")

    npass = sum(1 for r in results if r[0] == "PASS")
    summary = f"chat_battery: {npass}/{len(results)} pass, {fails} fail ({'inproc' if args.inproc else 'live'})"
    print("\n" + summary)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"\n### {time.strftime('%Y-%m-%d %H:%M')} — chat_battery ({'inproc' if args.inproc else 'live'})\n")
            f.write(f"- {summary}\n")
            for v, k, i, why in results:
                if v == "FAIL":
                    f.write(f"  - FAIL [{k}] `{i}` — {why}\n")
    except Exception:
        pass
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
