"""
Secrets / exposure detection — deterministic, precision-first.

TWO SCANNERS, DELIBERATELY SEPARATE
  find_secrets(text)   v1.3 legacy. 15 distinctive-prefix patterns, NO suppression. Stable contract:
                       ultron's `secret_scan` and the regression suite depend on its exact names and
                       on it reporting documented sample keys (AKIAIOSFODNN7EXAMPLE) as hits.
  scan_secrets(text)   the hunting scanner. 150 vendor formats across 23 categories, each carrying
                       severity / confidence / impact / remediation, behind a false-positive filter.

WHY THE SECOND ONE EXISTS
  Screening GhostJS on 2026-09-06 measured the gap: 15 patterns here against 150 available, and no
  false-positive suppression at all. Class 8 ("secrets / disclosure") was being verdicted with an
  instrument that could not see most of the surface. The corpus and the suppression logic are ported
  from trinetlayer/Ghost-Js-Burp-Extension (MIT) — patterns in data/secret_patterns.json, the filter
  re-implemented below from Entropy.java.

  What was NOT taken: its endpoint extractor (prefix-allowlist, narrower than find_endpoints) and its
  active fetcher (one hop HTML->JS, and its scope check is an OR that always allows same-host).
  See memory/repo-screen-ghostjs.md.

WHAT A HIT IS
  A pattern match is a LEAD, not a finding. It says a string has the SHAPE of a credential — not that
  the credential is live, in scope, or reachable. Confirming it is live means using it, which is a
  separate authorisation question. Report the exposure, never the successful use.

  🚨 Never paste a discovered key into a third-party "is this key live?" validator. That exfiltrates
  a target's credential to a vendor.

Pure functions, no network, no dependency. Authorized targets only.
"""
import json
import math
import os
import re
import sys
import time

# ---------------------------------------------------------------- legacy scanner (unchanged) ----

# (name, compiled regex) — every pattern has a service-specific prefix so a hit is high-confidence.
_SECRET_PATTERNS = [
    ("AWS access key id",        re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS session/temp key",     re.compile(r"ASIA[0-9A-Z]{16}")),
    ("Google API key",           re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("Google OAuth client id",   re.compile(r"[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com")),
    ("Slack token",              re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,48}")),
    ("Slack webhook",            re.compile(r"https://hooks\.slack\.com/services/T[0-9A-Z]+/B[0-9A-Z]+/[0-9A-Za-z]+")),
    ("Stripe live secret key",   re.compile(r"[sr]k_live_[0-9a-zA-Z]{20,40}")),
    ("GitHub token",             re.compile(r"gh[opsu]_[0-9A-Za-z]{36,}")),
    ("GitHub fine-grained PAT",  re.compile(r"github_pat_[0-9A-Za-z_]{60,}")),
    ("SendGrid API key",         re.compile(r"SG\.[0-9A-Za-z_-]{22}\.[0-9A-Za-z_-]{43}")),
    ("Twilio API/account SID",   re.compile(r"(?:SK|AC)[0-9a-fA-F]{32}")),
    ("Mailgun key",              re.compile(r"key-[0-9a-zA-Z]{32}")),
    ("Firebase cloud-msg key",   re.compile(r"AAAA[A-Za-z0-9_-]{7}:[A-Za-z0-9_-]{140}")),
    ("Private key block",        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("Hard-coded JWT",           re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]

# Backticks are a DELIMITER and `:{}$` are PATH characters, both added 2026-09-06 after a construct
# benchmark measured what the old class could not see: ES6 template literals (`/api/v2/entity/
# ${id}/filing`) and colon-templated routes (/filing/:ay/:eindex/:eid — ClearTax's split-brain-authz
# route, which we found by hand because this regex could not). jsluice and GhostJS are BOTH blind to
# template literals; this is the one JS-extraction case where we now beat them.
# FP check before landing: 37 real files / 223 KB -> +9 endpoints, 0 junk, 0 lost.
_ENDPOINT_RE = re.compile(r"""["'`](/[a-zA-Z0-9_][a-zA-Z0-9_./?=&%:{}$-]{2,120})["'`]""")

# Sensitive files the caller GETs on the base host; (path, [content signatures that confirm exposure]).
SENSITIVE_PATHS = [
    (".git/config",   ["[core]", "repositoryformatversion"]),
    (".git/HEAD",     ["ref: refs/"]),
    (".env",          ["=", "APP_", "DB_", "SECRET", "KEY", "PASSWORD"]),
    (".DS_Store",     ["Bud1", "\x00\x00\x00\x01Bud1"]),
    (".svn/entries",  ["dir", "svn:"]),
    ("config.json.bak", ["{"]),
    ("backup.sql",    ["INSERT INTO", "CREATE TABLE"]),
]


def find_secrets(text: str):
    """[(name, matched-substring)] for hard-coded secrets in `text`. De-duped by match.

    Legacy contract — no false-positive filter. Documented sample credentials ARE reported, because
    a caller probing a live host needs to see that the string is present in the response.
    """
    out, seen = [], set()
    for name, rx in _SECRET_PATTERNS:
        for m in rx.findall(text or ""):
            frag = m if isinstance(m, str) else (m[0] if m else "")
            if frag and frag not in seen:
                seen.add(frag)
                out.append((name, frag))
    return out


def find_endpoints(text: str):
    """Distinct path strings baked into JS/HTML — attack surface the crawler may have missed."""
    return sorted({m for m in _ENDPOINT_RE.findall(text or "")
                   if not m.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".woff", ".woff2", ".ico"))})


def file_signature(path: str, body: str) -> bool:
    """True if `body` matches a known signature for sensitive `path` (confirms real exposure, not a 200 SPA)."""
    for p, sigs in SENSITIVE_PATHS:
        if path.endswith(p):
            return any(s in (body or "") for s in sigs)
    return False


# ------------------------------------------------------- the 150-pattern corpus + FP filter ----

_CORPUS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data",
                            "secret_patterns.json")
_corpus = None            # lazily loaded; (list-of-(meta, compiled), meta-dict)


def corpus():
    """[(meta, compiled-regex)] for the full pattern set, plus the corpus _meta block.

    Compiles on load and raises if the file's own claimed count disagrees with what is present. An
    extractor whose output is a COUNT must make a wrong count loud (pb0712) — a silently short corpus
    reads exactly like a clean target.
    """
    global _corpus
    if _corpus is not None:
        return _corpus
    with open(_CORPUS_PATH, encoding="utf-8") as fh:
        doc = json.load(fh)
    meta = doc["_meta"]
    rows = []
    for p in doc["patterns"]:
        flags = 0
        if p.get("ignorecase"):
            flags |= re.IGNORECASE
        if p.get("multiline"):
            flags |= re.MULTILINE
        if p.get("dotall"):
            flags |= re.DOTALL
        rows.append((p, re.compile(p["source"], flags)))
    if len(rows) != meta["compiled"]:
        raise RuntimeError("secret_patterns.json self-check FAILED: %d patterns present, _meta.compiled "
                           "claims %d" % (len(rows), meta["compiled"]))
    _corpus = (rows, meta)
    return _corpus


def shannon(s: str) -> float:
    """Shannon entropy in bits per character."""
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    out = 0.0
    for c in freq.values():
        p = c / n
        out -= p * math.log2(p)
    return out


# Documented sample credentials that appear in tutorials and READMEs.
_KNOWN_EXAMPLES = {
    "AKIAIOSFODNN7EXAMPLE",
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "ASIAIOSFODNN7EXAMPLE",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0"
    "IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
}
_KNOWN_EXAMPLE_FRAGMENTS = ("EXAMPLEKEY", "AKIAIOSFODNN7EXAMPLE")

# Keys that are public BY DESIGN — shipping them client-side is the intended behaviour, so reporting
# one is a false report, not a low-severity one.
_PUBLIC_BY_DESIGN = [
    re.compile(r"^pk_(?:live|test)_[A-Za-z0-9]{8,}$"),
    re.compile(r"^6L[0-9A-Za-z_-]{38}$"),                       # reCAPTCHA site key
    re.compile(r"^p(?:k|ub)_[A-Za-z0-9]{8,}$"),
]

_COMMON_FP = [
    re.compile(r"^[0-9a-f]{32}$", re.I),
    re.compile(r"^0{20,}$"),
    re.compile(r"^1{20,}$"),
    re.compile(r"^a{20,}$", re.I),
    re.compile(r"^x{10,}$", re.I),
    re.compile(r"^(abc|123|test|demo|example|sample|default|changeme|password|secret|admin)", re.I),
    re.compile(r"^(undefined|null|none|empty|todo|fixme|placeholder|insert|your)", re.I),
    re.compile(r"^[A-Za-z]+_[A-Za-z]+_[A-Za-z]+$"),
    re.compile(r"^[a-z]{2,}(?:-[a-z]{2,}){1,}$"),                # kebab slug
    re.compile(r"^https?://localhost", re.I),
    re.compile(r"^https?://127\.0\.0\.", re.I),
    re.compile(r"^https?://0\.0\.0\.0", re.I),
    re.compile(r"^[a-z]+=[\da-f]{32}$", re.I),
    re.compile(r"^(session|cookie|token|csrf|nonce|hash|sid|id)=", re.I),
]
_HEX32 = r"^[0-9a-f]{32}$"

# 32 hex chars is junk for most types and the REAL format for these — the filter has to be name-aware
# or it silently deletes ten vendors' worth of true positives.
_HEX32_EXEMPT = {
    "Subscription / Access Key", "Algolia Admin API Key", "Twilio Auth Token", "Datadog API Key",
    "Facebook App Secret", "Agora App Certificate", "Rollbar Access Token", "Bugsnag API Key",
    "Fastly API Token", "Plaid Client Secret",
}

_PLACEHOLDER_MARKERS = (
    "example", "sample", "placeholder", "your_", "yourkey", "your-key", "changeme", "change_me",
    "redacted", "dummy", "test_key", "testkey", "lorem", "foobar", "insert_your", "replace_with",
    "somekey", "fakekey", "notreal", "<your", "enter_your", "xxxxx",
)

_SLASH_PATH = re.compile(r"^/[A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)+$")

# `[type=password]`, `[data-foo="bar"]`, `[aria-hidden]` -- markup selectors, never credentials.
_CSS_SELECTOR = re.compile(r"^\[[A-Za-z_:][\w:.-]*(?:[~|^$*]?=[^\]]*)?\]$")

# An absolute URL into a public docs/help site is not an "internal" anything.
_PUBLIC_DOC_URL = re.compile(r"^https?://[^/]*(?:developers?|docs?|help|support|learn|api-docs)\."
                             r"[^/]+/|^https?://[^/]+/(?:documentation|docs|help)/", re.I)
_ANGLE_TOKEN = re.compile(r".*<[a-zA-Z_]+>.*")

_COMMON_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "will", "would", "could", "should", "may", "might", "shall", "can", "to", "of",
    "in", "for", "on", "with", "at", "by", "from", "as", "into", "through", "please", "enter",
    "type", "input", "provide", "must", "field", "required", "your", "my", "this", "that", "these",
    "those", "it", "you", "we", "and", "or", "if", "not", "no", "all", "each", "some", "click",
    "here", "select",
}


def _is_ui_text(v: str) -> bool:
    words = v.strip().split()
    if len(words) < 4:
        return False
    common = sum(1 for w in words if w.lower() in _COMMON_WORDS)
    return common / len(words) >= 0.4


def _strip_affixes(v: str) -> str:
    s = re.sub(r"^[\"'`]+|[\"'`]+$", "", v)
    us = s.rfind("_")
    if 0 <= us < len(s) - 8:
        s = s[us + 1:]
    return s


def is_likely_false_positive(value, name="", strict=False) -> bool:
    """True when `value` is a documented sample, a public-by-design key, a placeholder, UI text, or
    low-entropy junk. `name` enables the format-aware exemptions; `strict` tightens generic captures.

    ⚠️ Suppression is not proof of absence. A value dropped here was never verdicted — it was never
    looked at. Anything this returns True for is UNMEASURED, not clean.
    """
    if value is None:
        return True
    v = value.strip()
    if len(v) < 6:
        return True

    if v in _KNOWN_EXAMPLES:
        return True
    if any(frag in v for frag in _KNOWN_EXAMPLE_FRAGMENTS):
        return True

    # Klaviyo's PRIVATE key also starts pk_ — the one vendor where the public-by-design shape lies.
    if name != "Klaviyo Private Key":
        if any(p.search(v) for p in _PUBLIC_BY_DESIGN):
            return True

    hex32_exempt = name in _HEX32_EXEMPT
    for p in _COMMON_FP:
        if hex32_exempt and p.pattern == _HEX32:
            continue
        if p.search(v):
            return True

    lower = v.lower()
    if any(t in lower for t in ("${", "{{", "%s", "process.env", "import.meta")):
        return True
    if _ANGLE_TOKEN.match(v):
        return True
    if any(m in lower for m in _PLACEHOLDER_MARKERS):
        return True

    # A CSS attribute selector is never a credential. `[type=password]` scored HIGH on the
    # "Hardcoded Password" pattern while sitting in a list beside [type=checkbox] and [type=radio]
    # -- found in a real bundle sweep 2026-09-07, not invented.
    if _CSS_SELECTOR.match(v):
        return True
    # A link into someone's public documentation is not an internal endpoint. The corpus's
    # "Internal API Endpoint" pattern matched a developers.facebook.com/documentation/... URL.
    if _PUBLIC_DOC_URL.search(v):
        return True

    if len(v) > 10 and len(set(v)) <= 3:
        return True
    if len(v) >= 16 and shannon(v) < 2.0:
        return True
    if _is_ui_text(v):
        return True
    if _SLASH_PATH.search(v):
        return True

    if strict:
        if re.search(r"\s", v):
            return True
        core = _strip_affixes(v)
        if len(core) >= 12 and shannon(core) < 3.0:
            return True
    return False


def _strict_for(meta) -> bool:
    """Generic capture patterns (loose 'api_key = ...' shapes) are the ones that manufacture
    placeholder hits, so they get the tighter checks."""
    n = meta["name"].lower()
    return "hardcoded" in n or "generic" in n or meta["confidence"] <= 80


def _value_of(m):
    """Prefer the first non-empty capture group — that is the secret; group 0 includes the key name."""
    for g in range(1, (m.re.groups or 0) + 1):
        try:
            grp = m.group(g)
        except IndexError:
            break
        if grp and grp.strip():
            return grp
    return m.group(0)


def mask(value: str) -> str:
    """Masked for any output that leaves this machine. Raw values are for the operator's screen only."""
    if not value:
        return ""
    v = value.strip()
    if len(v) <= 8:
        return v[0] + "***"
    return "%s...%s (%d chars)" % (v[:4], v[-4:], len(v))


def scan_secrets(text, url="", fp_filter=True, max_chars=5_000_000, budget_s=2.5,
                 per_pattern_cap=500):
    """The hunting scanner: 150 vendor formats, false-positive filtered.

    Returns [{name, category, severity, confidence, value, masked, url, line, snippet}] sorted most
    severe first. `fp_filter=False` shows what the filter is eating — use it once per target before
    trusting a silent result, the same way a probe ships with a positive control.
    """
    rows, _meta = corpus()
    if not text:
        return []
    body = text[:max_chars]
    deadline = time.monotonic() + budget_s
    out, seen = [], set()
    for meta, rx in rows:
        if time.monotonic() > deadline:
            break
        strict = _strict_for(meta)
        try:
            for i, m in enumerate(rx.finditer(body)):
                if i >= per_pattern_cap:
                    break
                value = _value_of(m)
                if not value or not value.strip():
                    continue
                value = value.strip()
                if fp_filter and is_likely_false_positive(value, meta["name"], strict):
                    continue
                key = (meta["name"], value, url)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"name": meta["name"], "category": meta["category"],
                            "severity": meta["severity"], "confidence": meta["confidence"],
                            "value": value, "masked": mask(value), "url": url,
                            "line": body.count("\n", 0, m.start()) + 1,
                            "snippet": _snippet(body, m.start(), m.end()),
                            "impact": meta["impact"], "remediation": meta["remediation"]})
        except (RuntimeError, RecursionError):
            continue          # one pathological body must never take the scan down
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    out.sort(key=lambda f: (order.get(f["severity"], 5), -f["confidence"]))
    return out


def _snippet(text, start, end):
    s = re.sub(r"\s+", " ", text[max(0, start - 40):min(len(text), end + 40)]).strip()
    return s[:200] + "..." if len(s) > 200 else s


def scan_files(paths, fp_filter=True):
    """Scan captured JS/HTML/JSON already on disk. The hunt path: mine the bundles, then read them
    here — no requests are made, so nothing about this touches the target."""
    findings = []
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            continue
        findings.extend(scan_secrets(body, url=p, fp_filter=fp_filter))
    return findings


def main(argv):
    if len(argv) < 2:
        print("usage: python -m core.secrets <file-or-dir> [...] [--raw] [--no-filter]")
        print("       --raw        print unmasked values (operator screen only, never a report)")
        print("       --no-filter  show what the false-positive filter is suppressing")
        return 2
    raw = "--raw" in argv
    fp_filter = "--no-filter" not in argv
    targets = [a for a in argv[1:] if not a.startswith("--")]

    paths = []
    for t in targets:
        if os.path.isdir(t):
            for root, _dirs, files in os.walk(t):
                paths += [os.path.join(root, f) for f in files
                          if f.lower().endswith((".js", ".mjs", ".html", ".htm", ".json", ".map"))]
        else:
            paths.append(t)

    _rows, meta = corpus()
    print("corpus: %d patterns (source %d, failed %d) | scanning %d file(s) | fp-filter %s"
          % (meta["compiled"], meta["in_source"], len(meta["failed"]), len(paths),
             "ON" if fp_filter else "OFF"))
    findings = scan_files(paths, fp_filter=fp_filter)
    if not findings:
        print("no matches. NOTE: silence here is only readable if the corpus self-check passed above "
              "and the files really are the bundles you meant to scan.")
        return 0
    for f in findings:
        print("%-9s %-34s %-26s conf %3d  %s"
              % (f["severity"].upper(), f["name"], f["category"][:26], f["confidence"],
                 f["value"] if raw else f["masked"]))
        print("          %s:%d  %s" % (f["url"], f["line"], f["snippet"][:110]))
    by_sev = {}
    for f in findings:
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    print("=== %d finding(s): %s" % (len(findings),
                                     ", ".join("%s %d" % (k, v) for k, v in sorted(by_sev.items()))))
    print("Every row is a LEAD. A shape match is not a live credential, and confirming one is live "
          "by using it is a separate authorisation question.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
