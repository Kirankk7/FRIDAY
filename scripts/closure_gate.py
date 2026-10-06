#!/usr/bin/env python3
"""Refuse to commit a matrix that claims closure without a closure proof beside it.

Why a hook and not a rule. Of 22 standing rules, 16 have no enforcement owner, and the four
that drifted most in the last hunt are all in that 16 - including "no class called CLOSED
without a stated denominator". A rule the model invokes is a rule the model can skip, so this
one sits on `git commit` in the private doctrine mirror, which is where matrices are actually
tracked and therefore where a closure claim becomes durable.

The specific failure it exists to stop, observed five times: the hunt is declared complete, the
operator asks "are you sure, check again", and a second pass finds more. The fix is not a
reminder to be thorough. It is that closure must carry a number - closure_delta, the count of
findings a deliberately different second pass turned up - and a non-zero delta reopens the class
rather than being argued down as minor.

    python scripts/closure_gate.py <matrix.md> [...]        # check named files
    python scripts/closure_gate.py --staged                 # check staged matrices (hook mode)

Exit 0 = every closure claim is backed. Non-zero = commit refused, with the reason.

Deliberately NOT checked: the presence of `NOT TESTED` rows. Every matrix on disk contains
them, correctly - a row reading NOT TESTED with a stated reason is honest coverage accounting,
not an open claim. A first version would have blocked every commit in the repository.
"""
import io
import json
import os
import re
import subprocess
import sys

# A hunt is declared closed when the header carries a real date rather than a dash.
_CLOSED_FIELD = re.compile(r"\|\s*closed\s*\|\s*([^|]*)\|", re.I)
_DATE = re.compile(r"20\d\d-\d\d-\d\d")
# "**classes FULLY CLOSED: 10 / 11**" - the claim that needs a denominator behind it
_FULLY = re.compile(r"classes\s+FULLY\s+CLOSED:\s*(\d+)\s*/\s*(\d+)", re.I)

VERDICTS = {"ENFORCED", "FALSIFIED", "UNTESTABLE", "UNREADABLE", "N/A", "NOT TESTED"}


def proof_path(matrix: str) -> str:
    """`coverage/foo_matrix.md` -> `coverage/foo_closure.json`."""
    d, base = os.path.dirname(matrix), os.path.basename(matrix)
    stem = re.sub(r"_matrix\.md$|\.md$", "", base)
    return os.path.join(d, stem + "_closure.json")


def read_claims(text: str):
    """-> (closed_date_or_empty, [(n, m), ...] every FULLY CLOSED claim in the file).

    A file may hold several claims - a superseded mid-hunt block plus the real close-out. The
    LAST one is authoritative, which is itself a convention worth stating rather than guessing:
    the audit found a matrix whose stale mid-hunt totals had been synced twice.
    """
    closed = ""
    m = _CLOSED_FIELD.search(text)
    if m and _DATE.search(m.group(1)):
        closed = _DATE.search(m.group(1)).group(0)
    return closed, [(int(a), int(b)) for a, b in _FULLY.findall(text)]


def check_proof(proof: dict, claim):
    """-> [reasons]. Validates the proof against itself and against the matrix claim."""
    bad = []

    # Hunts closed before this gate existed. closure_delta was not a concept then, so there is
    # no number to record and inventing one would fabricate the single field this gate protects.
    # A grandfathered proof therefore asserts LESS, on purpose: it states that the verdicts live
    # in the matrix prose and were never machine-checked. It is a receipt for an unaudited
    # claim, not a passing grade, and it must say so in the file rather than by omission.
    if proof.get("grandfathered") is True:
        for key in ("grandfathered_reason", "grandfathered_date"):
            if not str(proof.get(key) or "").strip():
                bad.append("grandfathered proof missing `%s`" % key)
        if proof.get("closure_delta_measured") is not False:
            bad.append("grandfathered proof must set `closure_delta_measured: false` - saying "
                       "the number was never taken is the whole point of grandfathering it")
        if proof.get("migrated") is not False:
            bad.append("grandfathered proof must set `migrated: false`")
        return bad

    classes = proof.get("classes")
    if not isinstance(classes, list) or not classes:
        return ["closure proof has no `classes` list"]

    closed_ids = []
    for c in classes:
        cid = str(c.get("id", "?"))
        verdict = (c.get("verdict") or "").strip()
        delta = c.get("closure_delta")
        denom = (c.get("denominator") or "").strip()

        if verdict not in VERDICTS:
            bad.append("class %s: verdict %r is not in the fixed vocabulary" % (cid, verdict))
        if not denom:
            bad.append("class %s: no denominator stated - a verdict without one is an opinion" % cid)
        if not isinstance(delta, int):
            bad.append("class %s: closure_delta missing - the second pass was not run or not counted" % cid)
            continue

        fully = bool(c.get("fully_closed"))
        # `closure_delta` is the FINAL review's count and must be 0 to close. Earlier non-zero
        # passes are not errors in the proof - they are the measurement working: the class was
        # reopened, retested and closed again. They belong in `closure_delta_history` so the
        # count of reopenings survives, which is the number that says whether first-pass
        # methodology is improving across hunts.
        if fully and delta > 0:
            bad.append("class %s: fully_closed with a FINAL closure_delta=%d - a non-zero final "
                       "delta REOPENS the class. If it was found, fixed and retested, record the "
                       "earlier pass in closure_delta_history and set closure_delta to the last "
                       "review's count" % (cid, delta))
        hist = c.get("closure_delta_history")
        if hist is not None and (not isinstance(hist, list)
                                 or any(not isinstance(x, int) for x in hist)):
            bad.append("class %s: closure_delta_history must be a list of integers" % cid)
        if fully and verdict in ("NOT TESTED", "UNREADABLE"):
            bad.append("class %s: fully_closed while verdict is %s" % (cid, verdict))
        if fully:
            closed_ids.append(cid)

    # the matrix's own arithmetic must match the proof
    if claim:
        n, m = claim
        if len(classes) != m:
            bad.append("matrix claims a denominator of %d classes, proof lists %d" % (m, len(classes)))
        if len(closed_ids) != n:
            bad.append("matrix claims FULLY CLOSED %d/%d, proof marks %d class(es) fully_closed"
                       % (n, m, len(closed_ids)))

    if not (proof.get("second_pass") or {}).get("checklist"):
        bad.append("no `second_pass.checklist` - the closure review must state what it asked that "
                   "the first pass did not, or it is the first pass run twice")
    hyg = proof.get("hygiene") or {}
    for key in ("credentials_removed", "session_artefacts_removed", "bundle_carveout_ok"):
        if hyg.get(key) is not True:
            bad.append("hygiene.%s is not true - closure is blocked until the workspace is clean" % key)
    return bad


def check_file(matrix: str):
    """-> [reasons] for one matrix file."""
    try:
        text = io.open(matrix, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        return ["cannot read %s (%s)" % (matrix, exc)]

    closed, claims = read_claims(text)
    if not closed and not claims:
        return []                                  # an open hunt in progress - nothing to prove
    # A FULLY CLOSED claim of 0/N is not a closure claim, it is an honest in-progress count.
    claim = claims[-1] if claims else None
    if claim and claim[0] == 0 and not closed:
        return []
    if not closed and claim and claim[0] == 0:
        return []

    p = proof_path(matrix)
    if not os.path.exists(p):
        return ["claims closure (closed=%s%s) but %s does not exist" %
                (closed or "-", ", FULLY CLOSED %d/%d" % claim if claim else "",
                 os.path.basename(p))]
    try:
        proof = json.load(io.open(p, encoding="utf-8"))
    except Exception as exc:
        return ["%s is not valid json (%s)" % (os.path.basename(p), exc)]
    return check_proof(proof, claim)


def staged_matrices():
    """-> every matrix in the repo, when the commit touches coverage material at all.

    First version returned only the staged *matrix*.md paths. Demonstrating the hook exposed the
    hole: staging an UNCHANGED matrix plus a new proof matched nothing, the gate printed "no
    matrix staged", and a deliberately padded closure claim was committed. A gate that inspects
    only the file you happened to edit cannot see a claim that was already sitting there.

    So any staged path under coverage/ re-checks the whole set. It is seven files, and it also
    catches drift in matrices this commit never touched.
    """
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                         capture_output=True, text=True).stdout
    staged = [p for p in out.split("\n") if p.strip()]
    if not any(p.startswith("coverage/") or "matrix" in p.lower() or "closure" in p.lower()
               for p in staged):
        return []
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True).stdout.strip() or "."
    cov = os.path.join(root, "coverage")
    if not os.path.isdir(cov):
        return []
    return [os.path.join(cov, f) for f in sorted(os.listdir(cov))
            if f.endswith(".md") and "matrix" in f.lower()]


def main():
    args = sys.argv[1:]
    if args == ["--staged"]:
        targets = staged_matrices()
        if not targets:
            print("closure gate: no matrix staged.")
            return 0
    elif args:
        targets = args
    else:
        print(__doc__.strip().split("\n\n")[0])
        return 2

    failures = {}
    for t in targets:
        reasons = check_file(t)
        if reasons:
            failures[t] = reasons

    if not failures:
        print("closure gate: %d matrix file(s) checked, every closure claim is backed." % len(targets))
        return 0

    print("")
    print("  COMMIT BLOCKED — closure claimed without proof:")
    print("")
    for t, reasons in failures.items():
        print("    %s" % t)
        for r in reasons:
            print("      - %s" % r)
    print("")
    print("  A hunt may be closed. It may not be closed without a number behind it.")
    print("  Write the proof beside the matrix, then commit again.")
    print("  Override only if the claim is genuinely not a closure: git commit --no-verify")
    print("")
    return 1


if __name__ == "__main__":
    sys.exit(main())
