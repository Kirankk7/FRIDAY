"""Multi-corpus extraction with a MANDATORY not-yet-mined list.

Built after hunt #41, where one denominator - the count of in-scope hosts - was
corrected FOUR times in a single day:

    notes "66"  ->  Certificate Transparency "32"  ->  APK dex "148"  ->  +registry "157"

Every correction arrived from a corpus I had not yet mined. Not one came from
re-examining the number I had just defended. Each total looked complete at the time
and obviously partial in hindsight. Two of those four I had explicitly called final.

THE RULE, and the only thing this module exists to enforce:

    A count is not a denominator. A count PLUS the list of corpora that were not
    mined is a denominator.

So `Sweep.total` does not exist. There is no attribute anywhere on the result that
returns a bare number, because a bare number is exactly what gets pasted into a
report and defended. `Sweep.statement()` returns the count welded to its own
provenance and its own gaps:

    "157 hostnames from dex+assets+registry; NOT MINED: urlscan (capped 100/649),
     wayback, source-maps"

That sentence is hard to write down dishonestly. `157` on its own is not.

WHY NOT JUST "MINE EVERYTHING": because you cannot. urlscan caps at 100 of 649,
Common Crawl times out, GitHub code search needs a token, a Play-Store-gated app
cannot be logged into. The gap is permanent and the point is to CARRY it, not close
it. An unmined corpus is a stated blind spot; an unmentioned one is a false total.

Pairs with core/instrument_check.py: that validates the extractor can see anything
at all, this validates that the extractor was pointed at everything available.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

# --------------------------------------------------------------------------- patterns

def host_pattern(apex: str) -> re.Pattern:
    """Full hostnames under an apex. `apex` is a literal domain, not a regex."""
    return re.compile(
        rb"(?<![A-Za-z0-9.-])([a-z0-9][a-z0-9.-]{0,60}\." + re.escape(apex).encode() + rb")"
    )


def region_fragment_pattern(suffixes: Iterable[str]) -> re.Pattern:
    """Service-name FRAGMENTS that a client assembles into hosts at runtime.

    hunt #41: the APK held 148 of these and only 11 full hostnames. An extractor
    that matches full hostnames only reports 11 and looks like it worked.
    """
    alt = b"|".join(re.escape(s).encode() for s in suffixes)
    return re.compile(rb"(?<![A-Za-z0-9.-])([a-z][a-z0-9-]{2,40}-(?:" + alt + rb"))(?![a-z0-9-])")


API_PATH = re.compile(
    rb"[\"'`](/(?:api|v\d|auth|oauth|graphql|rest|internal|admin|user|profile|account"
    rb"|search|otp|verify|token|session|sso|callback|webhook|export|upload)"
    rb"[A-Za-z0-9/_\-.{}:$]{0,80})[\"'`]"
)


# --------------------------------------------------------------------------- corpora

@dataclass
class CorpusResult:
    name: str
    status: str              # MINED | ABSENT | BLOCKED | PARTIAL
    hits: set = field(default_factory=set)
    detail: str = ""
    units: int = 0           # files/entries actually read

    @property
    def counts(self) -> bool:
        return self.status in ("MINED", "PARTIAL")


class Corpus:
    """One source of truth. Knows how to say it was NOT mined, and why."""

    def __init__(self, name: str, fn: Callable[[], CorpusResult]):
        self.name = name
        self._fn = fn

    def run(self) -> CorpusResult:
        try:
            return self._fn()
        except FileNotFoundError as e:
            return CorpusResult(self.name, "ABSENT", detail=f"not present: {e}")
        except Exception as e:                                   # noqa: BLE001
            return CorpusResult(self.name, "BLOCKED", detail=f"{type(e).__name__}: {e}")


# ---- concrete extractors ---------------------------------------------------

def apk_corpus(apk: Path, pattern: re.Pattern, *, skip_prefixes=("lib/",)) -> CorpusResult:
    """EVERY zip entry, not just classes*.dex.

    hunt #41 mined dex only and missed a hostname sitting in
    assets/common_sender_id.json. res/ was 8 827 entries and arsc was 26 MB - both
    unread. Splitting the result by zone is what made that visible.
    """
    if not apk.exists():
        raise FileNotFoundError(apk)
    z = zipfile.ZipFile(apk)
    zones: dict[str, set] = {}
    units = 0
    for n in z.namelist():
        if any(n.startswith(p) for p in skip_prefixes):
            continue
        try:
            data = z.read(n)
        except Exception:                                        # noqa: BLE001
            continue
        units += 1
        found = {m.decode("utf-8", "replace") for m in pattern.findall(data)}
        if not found:
            continue
        if n.endswith(".dex"):
            zone = "dex"
        elif n == "resources.arsc":
            zone = "arsc"
        elif n.startswith("assets/"):
            zone = "assets"
        elif n.startswith("res/"):
            zone = "res"
        else:
            zone = "other"
        zones.setdefault(zone, set()).update(found)
    allhits = set().union(*zones.values()) if zones else set()
    breakdown = " ".join(f"{k}={len(v)}" for k, v in sorted(zones.items())) or "none"
    outside = allhits - zones.get("dex", set())
    note = f"{units} entries; {breakdown}"
    if outside:
        note += f"; {len(outside)} found OUTSIDE dex"
    return CorpusResult("apk", "MINED", allhits, note, units)


def tree_corpus(root: Path, pattern: re.Pattern, *, glob="**/*", name="tree") -> CorpusResult:
    if not root.exists():
        raise FileNotFoundError(root)
    hits, units = set(), 0
    for p in root.glob(glob):
        if not p.is_file():
            continue
        units += 1
        hits |= {m.decode("utf-8", "replace") for m in pattern.findall(p.read_bytes())}
    return CorpusResult(name, "MINED", hits, f"{units} files", units)


def har_corpus(har: Path, pattern: re.Pattern) -> CorpusResult:
    """Request URLs AND response bodies.

    A HAR mined for its URL list only is a sample of what the browser fetched.
    The bodies hold what the app can reach but did not call.
    """
    if not har.exists():
        raise FileNotFoundError(har)
    d = json.loads(har.read_text(encoding="utf-8", errors="replace"))
    entries = d["log"]["entries"]
    hits = set()
    bodied = 0
    for e in entries:
        hits |= {m.decode() for m in pattern.findall(e["request"]["url"].encode())}
        txt = (e.get("response", {}).get("content") or {}).get("text")
        if txt:
            bodied += 1
            hits |= {m.decode("utf-8", "replace") for m in pattern.findall(txt.encode("utf-8", "replace"))}
    detail = f"{len(entries)} entries, {bodied} with bodies"
    status = "MINED" if bodied else "PARTIAL"
    if not bodied:
        detail += " - NO response bodies stored, URL list only"
    return CorpusResult("har", status, hits, detail, len(entries))


def json_list_corpus(path: Path, name: str) -> CorpusResult:
    """A list the target itself publishes (service registry, sitemap, asset list)."""
    if not path.exists():
        raise FileNotFoundError(path)
    d = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(d, dict):
        d = [x for v in d.values() for x in (v if isinstance(v, list) else [v])]
    hits = {str(x) for x in d if isinstance(x, (str, int))}
    return CorpusResult(name, "MINED", hits, f"{len(hits)} entries", len(hits))


# --------------------------------------------------------------------------- sweep

@dataclass
class Sweep:
    results: list[CorpusResult]
    declared: list[str]          # every corpus that SHOULD be consulted for this target

    # deliberately no .total / .count / .__len__ - see module docstring

    @property
    def union(self) -> set:
        return set().union(*[r.hits for r in self.results if r.counts]) or set()

    @property
    def mined(self) -> list[str]:
        return [r.name for r in self.results if r.counts]

    @property
    def not_mined(self) -> list[str]:
        """Declared but ABSENT/BLOCKED, plus anything never attempted at all."""
        attempted = {r.name for r in self.results}
        gaps = [f"{r.name} ({r.status.lower()}: {r.detail})"
                for r in self.results if not r.counts]
        gaps += [f"{n} (never attempted)" for n in self.declared if n not in attempted]
        return gaps

    def statement(self, noun: str = "items") -> str:
        """The only way to get the number out. Count welded to provenance and gaps."""
        n = len(self.union)
        src = "+".join(self.mined) or "NOTHING"
        s = f"{n} {noun} from {src}"
        gaps = self.not_mined
        s += f"; NOT MINED: {'; '.join(gaps)}" if gaps else "; NOT MINED: none declared"
        return s

    def contribution(self) -> list[tuple[str, int, int]]:
        """(corpus, hits, UNIQUE-to-this-corpus). A corpus with 0 unique adds nothing;
        a corpus with many unique is proof the others were incomplete."""
        out = []
        for r in self.results:
            if not r.counts:
                continue
            others = set().union(*[o.hits for o in self.results
                                   if o.counts and o.name != r.name]) or set()
            out.append((r.name, len(r.hits), len(r.hits - others)))
        return sorted(out, key=lambda t: -t[2])

    def report(self, noun: str = "items") -> str:
        lines = [self.statement(noun), ""]
        lines.append(f"  {'corpus':<12}{'status':<10}{'hits':>7}{'unique':>8}  detail")
        uniq = {c: u for c, _, u in self.contribution()}
        for r in self.results:
            u = uniq.get(r.name, 0) if r.counts else 0
            lines.append(f"  {r.name:<12}{r.status:<10}{len(r.hits):>7}{u:>8}  {r.detail[:58]}")
        dead = [c for c, h, u in self.contribution() if u == 0 and h]
        if dead:
            lines.append(f"\n  redundant this run (0 unique): {', '.join(dead)}")
        return "\n".join(lines)


def sweep(corpora: list[Corpus], declared: list[str]) -> Sweep:
    return Sweep([c.run() for c in corpora], declared)


# --------------------------------------------------------------------------- selftest

def _selftest() -> int:
    import tempfile

    fails = []
    tmp = Path(tempfile.mkdtemp())

    apex = "example.com"
    pat = host_pattern(apex)

    # an APK whose ONLY unique host lives in assets/ - the hunt #41 miss, reproduced
    apk = tmp / "t.apk"
    with zipfile.ZipFile(apk, "w") as z:
        z.writestr("classes.dex", b"\x00api.example.com\x00cdn.example.com\x00")
        z.writestr("assets/cfg.json", b'{"h":"assets-only.example.com"}')
        z.writestr("res/x.xml", b"<x/>")
        z.writestr("lib/arm64-v8a/libx.so", b"skipped.example.com")

    har = tmp / "t.har"
    har.write_text(json.dumps({"log": {"entries": [
        {"request": {"url": "https://api.example.com/v1/x"},
         "response": {"content": {"text": "fetch('https://har-only.example.com/y')"}}}
    ]}}), encoding="utf-8")

    reg = tmp / "r.json"
    reg.write_text(json.dumps(["registry-only.example.com", "api.example.com"]), encoding="utf-8")

    s = sweep(
        [
            Corpus("apk", lambda: apk_corpus(apk, pat)),
            Corpus("har", lambda: har_corpus(har, pat)),
            Corpus("registry", lambda: json_list_corpus(reg, "registry")),
            Corpus("ct", lambda: (_ for _ in ()).throw(FileNotFoundError("no ct dump"))),
        ],
        declared=["apk", "har", "registry", "ct", "urlscan", "wayback"],
    )

    # 1. lib/ skipped
    if "skipped.example.com" in s.union:
        fails.append("lib/ was not skipped")

    # 2. the assets-only host is present - the actual regression under test
    if "assets-only.example.com" not in s.union:
        fails.append("assets-only host MISSED (the hunt #41 failure, unfixed)")

    # 3. corpora that only one source has
    for h in ("har-only.example.com", "registry-only.example.com"):
        if h not in s.union:
            fails.append(f"{h} missing - a corpus was not merged")

    # 4. the gap list must name BOTH the failed corpus and the never-attempted ones
    gaps = " ".join(s.not_mined)
    for want in ("ct", "urlscan", "wayback"):
        if want not in gaps:
            fails.append(f"not_mined omits {want}")

    # 5. THE CENTRAL INVARIANT: no bare-number accessor exists
    for attr in ("total", "count", "n"):
        if hasattr(s, attr):
            fails.append(f"Sweep exposes .{attr} - a bare number can be quoted without its gaps")
    try:
        len(s)                                                    # type: ignore[arg-type]
        fails.append("Sweep supports len() - same hazard")
    except TypeError:
        pass

    # 6. statement() must carry the count AND the gaps
    st = s.statement("hostnames")
    if "NOT MINED" not in st or "urlscan" not in st:
        fails.append(f"statement() lost its gap list: {st}")
    if not st.startswith(str(len(s.union))):
        fails.append("statement() does not lead with the count")

    # 7. unique-contribution must credit assets-bearing apk, har and registry
    uniq = {c: u for c, _, u in s.contribution()}
    if not (uniq.get("apk", 0) and uniq.get("har", 0) and uniq.get("registry", 0)):
        fails.append(f"contribution() wrong: {uniq}")

    print(s.report("hostnames"))
    print()
    if fails:
        for f in fails:
            print(f"  FAIL  {f}")
        print(f"\nselftest: {len(fails)} FAILED")
        return 1
    print("selftest: 7/7 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
