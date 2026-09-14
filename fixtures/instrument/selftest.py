"""Self-test for the instrument-side control.

Three cases, and the middle one is the whole point:

  1. healthy fixture + working instrument   -> INSTRUMENT_VERIFIED
  2. MALFORMED fixture + working instrument -> FIXTURE_INVALID   (instrument NOT blamed)
  3. healthy fixture + broken instrument    -> INSTRUMENT_UNVERIFIED

Case 2 is a regression test for a real bug: the fixture's fake Google key once had 38
characters after its prefix instead of 35, so a CORRECT scanner pattern rightly missed it
and a WORKING instrument was reported as failing. The control created the false negative
it existed to catch.

The format check that catches it must be ANCHORED. An unanchored fixed-length pattern
(`AIza[\\w-]{35}`) matches the first 35 characters of a 38-character token and passes a
malformed fixture — the check on the control needed a control of its own.

NOTE ON THIS FILE: case 2 mutates the fixture on disk. The restore MUST be in `finally`.
An earlier version of this test crashed between mutate and restore and left the broken
fixture in place, which the next run then backed up as if it were healthy.
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from core.instrument_check import verify, CONTRACTS, SPLIT_TOKEN  # noqa: E402

FIXTURE = os.path.join(HERE, "secret-positive-v1.txt")
GOOD_TOKEN = "AIza" + SPLIT_TOKEN + "Sy" + "JARVISfixtureNOTAREALKEY" + "0" * 9
BAD_TOKEN = "AIza" + SPLIT_TOKEN + "SyJARVIS-fixture-not-a-real-key-000000"   # 38 chars: the bug


def working_secret_scanner(text):
    pats = ["AKIA" + r"[0-9A-Z]{16}", "GOCSPX" + r"-[\w-]+", "ghp" + r"_\w+",
            "AIza" + r"[\w-]{35}", "xoxb" + r"-[\w-]+", "sk" + r"_live_\w+",
            r"eyJ[\w-]+\.eyJ[\w-]+\.[\w-]+", "BEGIN RSA PRI" + "VATE KEY"]
    out = []
    for p in pats:
        out += re.findall(p, text)
    return out


def broken_scanner(_text):
    return []            # ran, sent nothing, found nothing -> the failure this all exists for


def main() -> int:
    fails = []

    r1 = verify("secret_scan", working_secret_scanner)
    ok1 = r1.status == "INSTRUMENT_VERIFIED"
    print("1. healthy fixture + working instrument   ->", r1.status, "" if ok1 else "  <-- FAIL")
    if not ok1:
        fails.append("case1: " + r1.status + " " + r1.error)

    shutil.copy(FIXTURE, FIXTURE + ".bak")
    try:
        s = open(FIXTURE, encoding="utf-8").read()
        assert GOOD_TOKEN in s, "fixture does not contain the expected good token"
        open(FIXTURE, "w", encoding="utf-8").write(s.replace(GOOD_TOKEN, BAD_TOKEN))
        r2 = verify("secret_scan", working_secret_scanner)
        ok2 = r2.status == "FIXTURE_INVALID"
        print("2. MALFORMED fixture + working instr.    ->", r2.status,
              "" if ok2 else "  <-- FAIL (instrument wrongly blamed)")
        if not ok2:
            fails.append("case2: expected FIXTURE_INVALID, got " + r2.status)
    finally:
        shutil.move(FIXTURE + ".bak", FIXTURE)          # MUST run even on exception

    r3 = verify("secret_scan", broken_scanner)
    ok3 = r3.status == "INSTRUMENT_UNVERIFIED"
    print("3. healthy fixture + broken instrument   ->", r3.status, "" if ok3 else "  <-- FAIL")
    if not ok3:
        fails.append("case3: " + r3.status)

    r4 = verify("secret_scan", working_secret_scanner)
    ok4 = r4.status == "INSTRUMENT_VERIFIED"
    print("4. fixture restored intact               ->", r4.status, "" if ok4 else "  <-- FAIL")
    if not ok4:
        fails.append("case4: fixture NOT restored - " + r4.status)

    print()
    if fails:
        print("SELFTEST FAILED:")
        for f in fails:
            print("   -", f)
        return 1
    print("SELFTEST PASSED - the control, and the control on the control, both work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
