"""Instrument-side positive control.

Our existing control (HUNT_PROTOCOL §4) validates the TARGET: an object we own, through
the same code path, that MUST succeed. It cannot see an instrument that never ran.

This validates the INSTRUMENT: a local fixture carrying known-positive markers that a
working extractor must recover. It exists because of four real failures in two weeks:

  * bracket-named chunk downloads wrote 0 bytes while curl reported HTTP 200 (twice)
  * a CRLF-terminated URL list produced curl code 000 on 38 fetches, which looks exactly
    like being IP-blocked; a single control request disproved it
  * an IDOR "control" built from a GUID scraped off page HTML could never have succeeded,
    so six identical 404s proved nothing
  * a secret scan reported "0 hits" over 119 files with no filter-OFF control, and was
    correctly recorded PARTIAL rather than ENFORCED for exactly that reason

THE RULE, and the only thing that matters here:

    An instrument that fails its positive control may still report observations,
    but it CANNOT issue a trusted negative verdict.

Statuses are deliberately not booleans:
    INSTRUMENT_VERIFIED    - fixture markers recovered; a negative on real data is trustworthy
    INSTRUMENT_UNVERIFIED  - ran, did not recover the markers; negatives are BLOCKED
    INSTRUMENT_ERROR       - did not run at all; negatives are BLOCKED

Usage:
    from core.instrument_check import verify
    r = verify("secret_scan", my_scanner_fn)
    if not r.trusts_negative:
        # record UNREADABLE. Do not write "clean".
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Callable, Iterable

SPLIT_TOKEN = "<|>"   # separator inside fixture files; stripped on load

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "fixtures", "instrument")

# instrument name -> (fixture file, markers that a working instrument MUST recover)
CONTRACTS = {
    "secret_scan": (
        "secret-positive-v1.txt",
        # also split, for the same reason - joined by _m() below
        [("AKIA", "IOSFODNN7EXAMPLE"), ("GOCSPX", "-"), ("ghp", "_"), ("AIza", "Sy"),
         ("xoxb", "-"), ("sk", "_live_"), ("eyJ","hbGciOiJIUzI1NiJ9"),
         ("BEGIN RSA PRI", "VATE KEY")],
    ),
    "endpoint_extract": (
        "endpoints-positive-v1.js",
        [("/api/v1/fixture/plain", ""), ("/api/v1/fixture/template/", ""),
         ("/fixture/single-quoted", ""), ("/api/v1/fixture/in-fetch-call", "")],
    ),
}


@dataclass
class Result:
    instrument: str
    fixture: str
    executed: bool
    expected: int
    detected: int
    missing: list
    status: str
    trusts_negative: bool
    error: str = ""

    def __str__(self) -> str:
        head = f"[{self.status}] {self.instrument} / {self.fixture}"
        body = f"  recovered {self.detected}/{self.expected}"
        if self.missing:
            body += f"  MISSING: {', '.join(self.missing[:6])}"
        tail = ("  -> negatives TRUSTED" if self.trusts_negative
                else "  -> negatives BLOCKED: this instrument cannot report 'clean'")
        return "\n".join([head, body, tail])


def verify(instrument: str, run: Callable[[str], Iterable[str]]) -> Result:
    """`run` takes the fixture's text and returns whatever it found (any iterable of str).

    We do not care HOW it finds things — only that the known-positive markers appear
    somewhere in its output. That keeps this a control, not a test framework.
    """
    if instrument not in CONTRACTS:
        return Result(instrument, "-", False, 0, 0, [], "INSTRUMENT_ERROR", False,
                      f"no contract defined for '{instrument}'")

    fixture, parts = CONTRACTS[instrument]
    markers = ["".join(p) for p in parts]
    path = os.path.join(FIXTURE_DIR, fixture)
    try:
        # Markers are stored SPLIT by SPLIT_TOKEN so no secret-shaped literal is ever committed
        # to this repo (GitHub push-protection rejects them, and rightly so). Reassemble here.
        text = open(path, encoding="utf-8").read().replace(SPLIT_TOKEN, "")
    except OSError as e:
        return Result(instrument, fixture, False, len(markers), 0, markers,
                      "INSTRUMENT_ERROR", False, f"fixture unreadable: {e}")

    try:
        found = list(run(text))
    except Exception as e:                                  # noqa: BLE001 - any failure is a failure
        return Result(instrument, fixture, False, len(markers), 0, markers,
                      "INSTRUMENT_ERROR", False, f"{type(e).__name__}: {e}")

    blob = "\n".join(str(x) for x in found)
    missing = [m for m in markers if m not in blob]
    detected = len(markers) - len(missing)
    ok = not missing
    return Result(instrument, fixture, True, len(markers), detected, missing,
                  "INSTRUMENT_VERIFIED" if ok else "INSTRUMENT_UNVERIFIED", ok)


def as_json(r: Result) -> str:
    return json.dumps(asdict(r), indent=1)


if __name__ == "__main__":
    import re
    import sys

    # Self-check: a deliberately BROKEN instrument must be caught, and a working one passed.
    def broken(_text):
        return []                                   # the "ran, found nothing, reported clean" failure

    def working_secrets(text):
        pats = ['AKIA' + r'[0-9A-Z]{16}', 'GOCSPX' + r'-[\w-]+', 'ghp' + r'_\w+',
                'AIza' + r'[\w-]+', 'xoxb' + r'-[\w-]+', 'sk' + r'_live_\w+',
                r'eyJ[\w-]+\.[\w-]+\.[\w-]+', 'BEGIN RSA PRI' + 'VATE KEY']
        out = []
        for p in pats:
            out += re.findall(p, text)
        return out

    print(verify("secret_scan", broken)); print()
    print(verify("secret_scan", working_secrets))
    sys.exit(0 if verify("secret_scan", working_secrets).trusts_negative else 1)
