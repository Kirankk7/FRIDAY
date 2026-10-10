#!/usr/bin/env python3
"""Validate a browser-console batch BEFORE the operator pastes it.

Exists because of a measured cost: hunt #43 burned 8 operator pastes to close
2 classes. Four of those were one probe family - each batch answered a single
question and carried no control, so every surprise cost another round trip.

This does NOT make a batch correct. It refuses the failure shapes that are
mechanically detectable, and it makes the undetectable ones cheaper by
requiring every batch to be self-describing.

Exit 0 = contract satisfied. Non-zero = do not hand this to the operator.
"""
import re, subprocess, sys, shutil, json, os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.control_event import emit as _emit  # noqa: E402

# --- the contract. Each rule names the real failure it comes from.
DESTRUCTIVE = re.compile(r"\b(DELETE|PUT)\b|method\s*:\s*[\"'](DELETE|PUT)", re.I)
OFFSITE     = re.compile(r"""fetch\(\s*[\"'`]https?://""", re.I)
HAS_CONTROL = re.compile(r"CONTROL|control", re.S)
HAS_RAW     = re.compile(r"slice\(|JSON\.stringify|textContent|innerText")
# NB: must cross parentheses - the first version used [^)]* and silently
# matched nothing on any line containing a call, which is most of them.
BARE_BOOL   = re.compile(r"\?\s*[\"'][^\"']{1,40}[\"']\s*:\s*[\"'][^\"']{0,40}[\"']")

def check(path):
    src = open(path, encoding="utf-8").read()
    fails, warns = [], []

    # 1. syntax - the cheapest class, and node settles it for free
    node = shutil.which("node")
    if node:
        r = subprocess.run([node, "--check", path], capture_output=True, text=True)
        if r.returncode != 0:
            fails.append("SYNTAX: " + (r.stderr.strip().splitlines() or ["?"])[0])
    else:
        warns.append("node absent - syntax UNVERIFIED (not the same as valid)")

    # 2. scope. A console batch runs in the operator's authenticated session;
    #    an absolute URL there sends their cookies somewhere we did not intend.
    if OFFSITE.search(src):
        fails.append("SCOPE: absolute http(s) fetch - console batches must be same-origin relative")

    # 3. destructive verbs need to be deliberate, never incidental
    if DESTRUCTIVE.search(src) and "ALLOW_DESTRUCTIVE" not in src:
        fails.append("SAFETY: DELETE/PUT present without an explicit ALLOW_DESTRUCTIVE marker")

    # 4. pb0767 - an instrument that cannot fail its own control cannot
    #    issue a trusted negative.
    if not HAS_CONTROL.search(src):
        fails.append("CONTROL: no positive control in the batch (pb0767)")

    # 5. I-34 - four of eight false instruments died the moment raw context
    #    replaced a boolean. Require raw context in the output.
    if not HAS_RAW.search(src):
        fails.append("EVIDENCE: prints no raw context (no slice/stringify/textContent)")

    # 6. a bare ternary verdict is the exact shape that produced the
    #    HTML-injection false positive and the visType wrong ENFORCED
    tern = BARE_BOOL.findall(src)
    if tern:
        warns.append("%d ternary verdict string(s) - each must be accompanied by the bytes it judged, not stand alone" % len(tern))

    return fails, warns

def main():
    _t0 = time.time()
    _me = os.path.abspath(__file__)
    if len(sys.argv) < 2:
        print("usage: console_batch.py <batch.js> [...]")
        _emit("console_batch", "ERROR", "no batch file given", rule_id="usage",
              duration_ms=int((time.time()-_t0)*1000), tool_file=_me)
        return 2
    bad = 0
    for p in sys.argv[1:]:
        fails, warns = check(p)
        print("=== %s" % p)
        for w in warns: print("  WARN  %s" % w)
        for f in fails: print("  FAIL  %s" % f)
        if fails:
            bad = 1
            print("  -> DO NOT HAND TO OPERATOR")
        else:
            print("  -> contract satisfied (%d warning(s))" % len(warns))
    _emit("console_batch", "BLOCK" if bad else "PASS",
          "contract violated" if bad else "contract satisfied",
          rule_id="console_batch_contract",
          context="%d file(s)" % len(sys.argv[1:]),
          duration_ms=int((time.time()-_t0)*1000), tool_file=_me)
    return bad

if __name__ == "__main__":
    sys.exit(main())
