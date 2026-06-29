#!/usr/bin/env python
"""Chat reply review surface — heuristic flags + LLM-judge on flagged-only -> CHAT_REVIEW.md.

Reads data/chat_replies/<run_id>.jsonl produced by `chat_battery.py --record`,
applies cheap heuristic flags to surface ugliness (raw paths, JSON dumps, terse,
walls, generic 'Done.', leaks), optionally runs an LLM judge on flagged-only with
a tight rubric (naturalness 1-5 + raw_data_leak + suggested_rewrite), and emits
`CHAT_REVIEW.md` sorted worst-first for human review + fix.

Diff mode: compare two runs (old vs new) to receipt polish-over-time.

Run:
  python scripts/chat_review.py --run RUN_ID                  # flag-only review
  python scripts/chat_review.py --run RUN_ID --judge          # + LLM judge on flagged
  python scripts/chat_review.py --diff OLD_RUN NEW_RUN        # delta scoreboard
"""
import os, sys, json, re, argparse, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPLIES_DIR = os.path.join(ROOT, "data", "chat_replies")
OUT = os.path.join(ROOT, "CHAT_REVIEW.md")

_PATH_ONLY = re.compile(r"^([A-Za-z]:[\\/]|/)[\w\-./\\ ]+\.(txt|md|pdf|json|csv|log|py|html|jpg|png|mp4)$")
_JSON_LIKE = re.compile(r"^\s*[\{\[]")
_GENERIC = {"done.", "done", "completed.", "completed", "ok.", "ok", "success.", "success", "yes.", "no."}
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_TAGLEAK = re.compile(r"\[(AGENT|ULTRON|ATHENA|FRIDAY|SYSTEM)\b")
_FASTACK_OK = re.compile(r"^(got it|done|sure|okay|ok|alright|copy that|on it|right away)[,\.! ]", re.I)
# Short replies that are CORRECT one-liners (hash, decoded text, action ack) — exempt from terse.
_TERSE_OK = re.compile(
    r"^(MD5|SHA\d+|ROT13|Decoded|JWT decoded|Base\d+|Hex|URL|HTML|Unicode|Caesar|Morse):"
    r"|^In \w+, that's:"                             # vision translate
    r"|^Opening "                                    # veronica open_url / app
    r"|^Note saved, boss:"                           # friday add_note
    r"|^Task added, boss:"                           # friday add_task
    r"|^Goal locked in, boss:"                       # friday add_goal
    r"|^Reminder set"                                # friday set_reminder
    r"|^Locked in, boss:"                            # edith store_memory
    r"|^Unknown currency"                            # vision currency error
    r"|^Translation failed:",                        # vision translate error
    re.I,
)


def flag(reply: str, agent: str, kind: str) -> list:
    """Heuristic flags pointing at polish-worthy replies. Empty list = looks fine."""
    flags = []
    r = (reply or "").strip()
    if not r:
        flags.append("empty")
        return flags
    if _PATH_ONLY.match(r):
        flags.append("raw_path")
    if _JSON_LIKE.match(r):
        flags.append("json_dump")
    if r.lower() in _GENERIC:
        flags.append("generic")
    if _ANSI.search(r):
        flags.append("ansi_leak")
    if _TAGLEAK.search(r):
        flags.append("tag_leak")
    words = r.split()
    # terse: <4 words AND not a known fast-ack AND not a complete one-liner result
    if len(words) < 4 and not _FASTACK_OK.match(r) and not _TERSE_OK.match(r):
        flags.append("terse")
    # wall: long + few sentence breaks (raw dump suspect)
    if len(r) > 600:
        body = r[len(r) // 10: -len(r) // 10]
        if body.count(".") + body.count("!") + body.count("?") < 3:
            flags.append("wall")
    return flags


def load_run(run_id: str) -> list:
    path = os.path.join(REPLIES_DIR, f"{run_id}.jsonl")
    if not os.path.exists(path):
        print(f"no such run: {path}")
        sys.exit(2)
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln, strict=False))
    return rows


def judge_one(row: dict) -> dict:
    """Single LLM judge call. Returns {score: 1-5, raw_data_leak: 0|1, rewrite: str}."""
    from core.llm import ask_llm_fast
    prompt = (
        "You are a strict assistant-reply quality judge. Score this REPLY on naturalness "
        "(1=robotic/raw-data, 5=Siri/Gemini-polished). Output ONE LINE of JSON only:\n"
        '{"score": <1-5>, "raw_data_leak": <0 or 1>, "rewrite": "<better reply, one sentence>"}\n\n'
        f"USER INPUT: {row['input']!r}\n"
        f"AGENT: {row.get('agent', '?')}\n"
        f"REPLY: {row.get('reply', '')[:600]!r}\n\nJSON:"
    )
    try:
        raw = ask_llm_fast(prompt, max_tokens=200) or ""
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            return json.loads(m.group(0))
    except Exception as e:
        return {"score": None, "error": str(e)[:60]}
    return {"score": None}


def emit_report(rows: list, judged: bool = False):
    flagged = []
    for r in rows:
        fls = flag(r.get("reply", ""), r.get("agent", ""), r.get("kind", ""))
        r["flags"] = fls
        if fls:
            flagged.append(r)

    if judged and flagged:
        print(f"judging {len(flagged)} flagged replies via LLM (this is the slow part)...")
        for i, r in enumerate(flagged[:50]):           # cap to 50 to bound cost
            print(f"  [{i+1}/{min(50, len(flagged))}] {r['input'][:40]!r}")
            r["judge"] = judge_one(r)

    flagged.sort(key=lambda r: (
        (r.get("judge", {}) or {}).get("score") or 99,
        -len(r.get("flags", [])),
        -(len(r.get("reply", ""))),
    ))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(f"# Chat Reply Review — {time.strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**{len(flagged)} flagged of {len(rows)} replies.** "
                f"Sorted worst-first; eyeball, decide fix, edit the agent.\n\n")
        if not flagged:
            f.write("No flagged replies — all clean.\n")
        for r in flagged:
            f.write(f"---\n### `{r['input']}`\n")
            f.write(f"- **agent**: `{r.get('agent') or '(none)'}` · **kind**: {r.get('kind','?')} · "
                    f"**flags**: {', '.join(r['flags']) or '-'} · "
                    f"**latency**: {r.get('latency_ms', 0)}ms\n")
            if r.get("judge"):
                j = r["judge"]
                f.write(f"- **judge**: score={j.get('score','?')}/5 "
                        f"raw_data_leak={j.get('raw_data_leak','?')}\n")
                if j.get("rewrite"):
                    f.write(f"- **suggested rewrite**: {j['rewrite']}\n")
            reply = (r.get("reply") or "").replace("`", "'")
            if len(reply) > 1500:
                reply = reply[:1500] + "\n…[truncated, total " + str(len(r['reply'])) + " chars]"
            f.write(f"\n```\n{reply}\n```\n\n")

    print(f"-> {OUT}  ({len(flagged)} flagged of {len(rows)})")


def emit_beforeafter(old_id: str, new_id: str, out_path: str = None):
    """Write a markdown showing input + before reply + after reply for every input
    whose reply text changed between two runs. The receipt of the polish loop."""
    out_path = out_path or os.path.join(ROOT, "CHAT_BEFORE_AFTER.md")
    old = {r["input"]: r for r in load_run(old_id)}
    new = {r["input"]: r for r in load_run(new_id)}
    common = sorted(set(old) & set(new))
    changed, polished, unchanged = [], [], []
    for inp in common:
        o, n = old[inp], new[inp]
        ot, nt = (o.get("reply") or "").strip(), (n.get("reply") or "").strip()
        if ot == nt:
            unchanged.append(inp); continue
        o_fls = flag(ot, o.get("agent", ""), o.get("kind", ""))
        n_fls = flag(nt, n.get("agent", ""), n.get("kind", ""))
        # "polished" = the reply changed AND old had flags AND new is cleaner
        if o_fls and len(n_fls) < len(o_fls):
            polished.append((inp, o, n, o_fls, n_fls))
        else:
            changed.append((inp, o, n, o_fls, n_fls))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Chat Polish — Before / After ({time.strftime('%Y-%m-%d %H:%M')})\n\n")
        f.write(f"Compares `{old_id}` (before) vs `{new_id}` (after).\n\n")
        f.write(f"- **polished**: {len(polished)} (reply changed, fewer flags)\n")
        f.write(f"- **changed**:  {len(changed)} (reply changed, same/more flags — usually LLM stochasticity)\n")
        f.write(f"- **unchanged**: {len(unchanged)}\n\n")
        if polished:
            f.write("## Polished — these are the wins\n\n")
            for inp, o, n, of, nf in polished:
                f.write(f"### `{inp}`\n")
                f.write(f"- **agent**: {o.get('agent')!r} -> {n.get('agent')!r} · "
                        f"**flags**: {of} -> {nf}\n\n")
                f.write("**Before:**\n```\n" + ((o.get('reply') or '').strip() or '(empty)') + "\n```\n\n")
                f.write("**After:**\n```\n" + ((n.get('reply') or '').strip() or '(empty)') + "\n```\n\n---\n\n")
        if changed:
            f.write("## Changed (no flag delta — LLM stochasticity or neutral rewrite)\n\n")
            for inp, o, n, of, nf in changed[:40]:
                f.write(f"### `{inp}`\n")
                f.write(f"- agent: {o.get('agent')!r} -> {n.get('agent')!r}\n\n")
                f.write("Before:\n```\n" + ((o.get('reply') or '').strip()[:400] or '(empty)') + "\n```\n")
                f.write("After:\n```\n" + ((n.get('reply') or '').strip()[:400] or '(empty)') + "\n```\n\n")
    print(f"-> {out_path}  ({len(polished)} polished, {len(changed)} other-changed, {len(unchanged)} unchanged)")


def emit_diff(old_id: str, new_id: str):
    old = {r["input"]: r for r in load_run(old_id)}
    new = {r["input"]: r for r in load_run(new_id)}
    common = sorted(set(old) & set(new))
    improved, regressed, same = [], [], []
    for inp in common:
        o_fls = flag(old[inp].get("reply", ""), old[inp].get("agent", ""), old[inp].get("kind", ""))
        n_fls = flag(new[inp].get("reply", ""), new[inp].get("agent", ""), new[inp].get("kind", ""))
        if len(o_fls) > len(n_fls):
            improved.append((inp, o_fls, n_fls))
        elif len(o_fls) < len(n_fls):
            regressed.append((inp, o_fls, n_fls))
        else:
            same.append(inp)
    print(f"\n=== chat_review diff: {old_id} -> {new_id} ===")
    print(f"  improved : {len(improved)}")
    print(f"  regressed: {len(regressed)}")
    print(f"  same     : {len(same)}")
    for inp, o, n in improved[:20]:
        print(f"  + {inp[:50]!r:52} {o} -> {n}")
    for inp, o, n in regressed[:20]:
        print(f"  - {inp[:50]!r:52} {o} -> {n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="run_id (data/chat_replies/<run_id>.jsonl)")
    ap.add_argument("--judge", action="store_true", help="LLM-judge flagged replies (slow)")
    ap.add_argument("--diff", nargs=2, metavar=("OLD", "NEW"), help="compare two runs")
    ap.add_argument("--beforeafter", nargs=2, metavar=("OLD", "NEW"),
                    help="emit CHAT_BEFORE_AFTER.md showing input + old reply + new reply")
    args = ap.parse_args()

    if args.diff:
        emit_diff(*args.diff)
        return
    if args.beforeafter:
        emit_beforeafter(*args.beforeafter)
        return
    if not args.run:
        ap.print_help(); sys.exit(2)
    rows = load_run(args.run)
    emit_report(rows, judged=args.judge)


if __name__ == "__main__":
    main()
