"""Lens Run — make "written before discussion" an auditable fact instead of a promise.

MILESTONE A (memory/milestone-hypothesis-origin.md) asks for one filed bug where the invariant lens
NAMED the field or invariant before either the operator or the assistant articulated it. Criterion 2 of
that milestone is the whole milestone:

    "Lens output is WRITTEN TO A TIMESTAMPED FILE BEFORE ANY DISCUSSION of that request. Without
     write-before-discuss the ordering is unauditable and the assistant is grading its own homework."

Every previous attempt to honour that has been a promise made in prose. A promise is not evidence: at
grading time there is nothing that distinguishes hypotheses written before the answer was known from
hypotheses written after. This module supplies the missing evidence and nothing else.

WHAT IT DOES
  new    stage one captured request into its own run directory, hash it, and emit the cold-session
         prompt. The hash pins WHICH request the run is about.
  seal   freeze the hypotheses file: record its sha256 and the UTC time it was frozen. After this point
         any edit is detectable, so a grade can be trusted.
  grade  attach an A/B/C verdict — and REFUSE to do so unless the run was sealed first.

WHAT IT DELIBERATELY DOES NOT DO
  It does not read, parse, or reason about the request. It does not generate hypotheses. It does not
  edit docs/INVARIANT_LENS.md, which is frozen until the first cold run completes (editing the lens
  against a request we have already reasoned about would contaminate the experiment it exists to run).
  The thinking is the cold session's job; this module only makes the ORDER of events provable.

Offline, stdlib-only, deterministic. Sends nothing.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

RUNS_DIR = os.path.join("workspace", "lens")

# The four questions and the grading buckets are RESTATED here, not imported, so the cold session can be
# handed a single self-contained prompt with no repo access. Keep in sync with docs/INVARIANT_LENS.md by
# hand — and only ever in the direction doc -> here.
_PROMPT = """You are analysing ONE captured HTTP request from an authorised security engagement.

You have no other context, and you must not ask for any. Do not speculate about the target's identity,
its business, or what was found on it previously. Work only from the bytes below.

Produce RANKED HYPOTHESES. Each one must name a SPECIFIC FIELD or a SPECIFIC SERVER INVARIANT.

The bar, and the reason most attempts fail it:
  BAD   "possible mass assignment"          <- names a vulnerability CLASS
  GOOD  "price_id is merchant-fixed but accepted from the client; candidate invariant: line items on a
         merchant-created order must be immutable to the buyer"   <- names something ONE TEST CAN FALSIFY

A class label is not a hypothesis. If a line could be written without having read this particular
request, delete it.

For EVERY field in the request, answer four questions:

 1. OWNERSHIP — is this value client-owned, server-derived, counterparty-fixed, or system-owned?
    The bug lives where something counterparty-fixed or system-owned turns out to be WRITABLE.

 2. UI EXPOSURE — does the interface expose a control for this field? A field present in the body with
    no control in the UI is high-suspicion: the server may be enforcing the UI's contract rather than
    its own invariant.

 3. WORST LEGAL VALUE — not a malformed value. The worst value that is still well-formed and that the
    schema would accept: 0, negative, max+1, a fraction, a duplicate element, an empty array, or
    ANOTHER OBJECT THIS SAME ACTOR LEGITIMATELY OWNS SOMEWHERE ELSE.

 4. STATE ASSUMPTIONS — what does this request assume about sequence? Is it sequential, atomic,
    single-use, ordered, idempotent? Name the assumption that would break under concurrency or replay.

OUTPUT FORMAT — write exactly this, nothing before or after:

  ## H1 <one-line invariant claim>
  field:      <exact field name from the request>
  ownership:  client | server-derived | counterparty-fixed | system
  ui:         exposed | not-exposed | unknown
  invariant:  <the server rule you believe SHOULD hold>
  falsify:    <the single request that would disprove it>
  confidence: high | medium | low

  ## H2 ...

Rank by how specific and falsifiable the hypothesis is, NOT by imagined severity.
If a field yields nothing, omit it. Emitting confident nonsense is worse than emitting less.

--------------------------- CAPTURED REQUEST ---------------------------
{capture}
------------------------------------------------------------------------
"""

_HYPOTHESES_STUB = """<!-- Written by the COLD session. Nothing else goes in this file. -->
<!-- Do not edit after `lens_run.py seal`. The seal is what makes the grade trustworthy. -->

"""


def _utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _manifest_path(run_dir):
    return os.path.join(run_dir, "MANIFEST.json")


def _load_manifest(run_dir):
    p = _manifest_path(run_dir)
    if not os.path.exists(p):
        raise SystemExit("not a lens run (no MANIFEST.json): %s" % run_dir)
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _save_manifest(run_dir, m):
    with open(_manifest_path(run_dir), "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=2)


def new(capture_path, label=None):
    """Stage a capture into its own run directory and emit the cold-session prompt."""
    with open(capture_path, encoding="utf-8", errors="replace") as fh:
        capture = fh.read()
    if not capture.strip():
        raise SystemExit("capture is empty: %s" % capture_path)

    digest = _sha(capture)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = "%s-%s" % (stamp, digest[:8])
    if label:
        name += "-" + "".join(c if c.isalnum() or c in "-_" else "-" for c in label)[:40]
    run_dir = os.path.join(RUNS_DIR, name)
    os.makedirs(run_dir, exist_ok=False)

    with open(os.path.join(run_dir, "request.txt"), "w", encoding="utf-8") as fh:
        fh.write(capture)
    with open(os.path.join(run_dir, "PROMPT.txt"), "w", encoding="utf-8") as fh:
        fh.write(_PROMPT.format(capture=capture))
    with open(os.path.join(run_dir, "HYPOTHESES.md"), "w", encoding="utf-8") as fh:
        fh.write(_HYPOTHESES_STUB)

    _save_manifest(run_dir, {
        "run": name,
        "created_utc": _utc(),
        "capture_sha256": digest,
        "capture_bytes": len(capture),
        "label": label,
        "state": "OPEN",
    })

    print("run:    %s" % run_dir)
    print("sha256: %s  (pins WHICH request this run is about)" % digest)
    print()
    print("NEXT, in this order — the order IS the experiment:")
    print("  1. open a COLD session: no hunt context, no lane list, no target name")
    print("  2. paste PROMPT.txt into it, verbatim and alone")
    print("  3. paste its reply into HYPOTHESES.md, unedited")
    print("  4. python -m core.lens_run seal %s" % run_dir)
    print("  5. ONLY THEN bring it back for grading")
    return run_dir


def seal(run_dir):
    """Freeze the hypotheses. Everything after this is auditable; everything before is not."""
    m = _load_manifest(run_dir)
    if m.get("state") != "OPEN":
        raise SystemExit("already sealed at %s — a run seals once" % m.get("sealed_utc"))

    hp = os.path.join(run_dir, "HYPOTHESES.md")
    with open(hp, encoding="utf-8") as fh:
        body = fh.read()
    if body.strip() == _HYPOTHESES_STUB.strip() or not body.strip():
        raise SystemExit("HYPOTHESES.md is still empty — nothing to seal")

    m["state"] = "SEALED"
    m["sealed_utc"] = _utc()
    m["hypotheses_sha256"] = _sha(body)
    m["hypotheses_bytes"] = len(body)
    _save_manifest(run_dir, m)

    print("SEALED %s" % m["sealed_utc"])
    print("hypotheses sha256: %s" % m["hypotheses_sha256"])
    print("Any later edit to HYPOTHESES.md now shows up as a hash mismatch on `verify`.")


def verify(run_dir):
    """Re-hash the hypotheses and report whether they still match the seal."""
    m = _load_manifest(run_dir)
    if m.get("state") == "OPEN":
        print("UNSEALED — this run cannot be graded and proves nothing about ordering.")
        return False
    with open(os.path.join(run_dir, "HYPOTHESES.md"), encoding="utf-8") as fh:
        now = _sha(fh.read())
    ok = now == m["hypotheses_sha256"]
    print("sealed:   %s" % m["sealed_utc"])
    print("expected: %s" % m["hypotheses_sha256"])
    print("actual:   %s" % now)
    print("INTACT" if ok else "MODIFIED SINCE SEAL — the grade below is not trustworthy")
    return ok


def grade(run_dir, bucket, note):
    """Attach the A/B/C verdict. Refuses on an unsealed or tampered run."""
    bucket = bucket.upper()
    if bucket not in ("A", "B", "C"):
        raise SystemExit("bucket must be A, B or C")
    m = _load_manifest(run_dir)
    if m.get("state") == "OPEN":
        raise SystemExit("run is not sealed — seal before grading, or the grade means nothing")
    if not verify(run_dir):
        raise SystemExit("refusing to grade a run that changed after sealing")

    m.setdefault("grades", []).append({
        "graded_utc": _utc(),
        "bucket": bucket,
        "note": note,
        "meaning": {
            "A": "novel hypothesis that SURVIVED verification -> this is the milestone",
            "B": "novel hypothesis that proved a FALSE POSITIVE -> records the lens's noise rate",
            "C": "nothing beyond what we already knew -> capability NOT demonstrated",
        }[bucket],
    })
    _save_manifest(run_dir, m)
    print("graded %s: %s" % (bucket, m["grades"][-1]["meaning"]))
    if bucket == "C":
        print("Do not rationalise a C into a pass. C is the honest default.")


def ls():
    """List every run and its state, so a C can never quietly disappear."""
    if not os.path.isdir(RUNS_DIR):
        print("no runs yet")
        return
    rows = []
    for name in sorted(os.listdir(RUNS_DIR)):
        d = os.path.join(RUNS_DIR, name)
        if not os.path.isfile(_manifest_path(d)):
            continue
        m = _load_manifest(d)
        g = m.get("grades") or []
        rows.append((name, m.get("state", "?"), g[-1]["bucket"] if g else "-"))
    if not rows:
        print("no runs yet")
        return
    print("%-52s %-8s %s" % ("run", "state", "grade"))
    for r in rows:
        print("%-52s %-8s %s" % r)
    buckets = [r[2] for r in rows if r[2] != "-"]
    if buckets:
        print()
        print("A=%d  B=%d  C=%d   (A is the milestone; B and C are still results)"
              % (buckets.count("A"), buckets.count("B"), buckets.count("C")))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        print("usage:")
        print("  python -m core.lens_run new <capture-file> [label]")
        print("  python -m core.lens_run seal <run-dir>")
        print("  python -m core.lens_run verify <run-dir>")
        print("  python -m core.lens_run grade <run-dir> <A|B|C> <note>")
        print("  python -m core.lens_run ls")
        return 1
    cmd = argv[1]
    if cmd == "new":
        new(argv[2], argv[3] if len(argv) > 3 else None)
    elif cmd == "seal":
        seal(argv[2])
    elif cmd == "verify":
        verify(argv[2])
    elif cmd == "grade":
        grade(argv[2], argv[3], " ".join(argv[4:]) or "(no note)")
    elif cmd == "ls":
        ls()
    else:
        raise SystemExit("unknown command: %s" % cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
