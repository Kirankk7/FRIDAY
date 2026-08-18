#!/usr/bin/env python3
"""
vdp_sweep.py - discover self-hosted vulnerability-disclosure programmes without Google.

Google caps results and every hunter shares the same index, so a public dork list finds
the most-dorked targets, not the least. RFC 9116 gives a better path: security.txt lives
at a well-known URI that exists to be fetched. One request per host over a domain list
covers ground no dork budget reaches.

Stage 1  fetch /.well-known/security.txt (fallback /security.txt), parse RFC 9116 fields.
Stage 2  --policy: fetch each Policy: URL and score it against the authorisation gate.

THE GATE (docs/VDP_DORKS.md): a policy page is authorisation only when it states
  scope + safe-harbour wording + a working intake channel.
This script SCORES those signals so a human can read the page. It never decides, and a
high score is not permission - read the policy before touching any host.

Usage
  python scripts/vdp_sweep.py domains.txt -o out.jsonl
  python scripts/vdp_sweep.py domains.txt -o out.jsonl --policy --rate 3
  python scripts/vdp_sweep.py --report out.jsonl

domains.txt: one host per line ("example.co.uk"), # comments ignored.
"""
import argparse
import html
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "vdp-sweep/1.0 (RFC9116 security.txt discovery; contact: {c})"

FIELDS = ("contact", "policy", "expires", "encryption", "acknowledgments",
          "preferred-languages", "canonical", "hiring")

# Every pattern below was tuned against REAL policy text, not guessed. The misses that
# forced each addition are named, because a silent false negative here reads as "no
# programme" and drops a live target on the floor.
SIGNALS = {
    # missed a real UK policy's "will not seek prosecution of any security researcher
    # who reports, in good faith and in accordance with this policy"
    "safe_harbour": re.compile(
        r"safe harbou?r"
        r"|will not (?:pursue|take|initiate|bring|seek)[^.]{0,60}(?:legal|prosecut|action|claim)"
        r"|(?:will )?not (?:be )?prosecut|no legal action|not (?:report|refer) you"
        r"|good.?faith[^.]{0,80}(?:research|report|accordance|polic)"
        r"|authoris(?:e|ed|ation)[^.]{0,40}(?:test|research)", re.I),
    # Missed hyphenated "in-scope". Also missed a bare "Scope" heading followed by a
    # domain list, which is how the strongest candidate of the first batch wrote it.
    # The negated class below must exclude NEWLINE, not DOT: a domain such as
    # *.example.ai is full of dots, so a dot-negated class stops at the first dot and
    # the whole alternation silently never fires.
    "scope": re.compile(
        r"\bin[- ]scope\b|\bout[- ]of[- ]scope\b"
        r"|scope of (?:this|the) (?:policy|programme|program)"
        r"|following (?:domains|assets|systems)|assets? (?:covered|in[- ]scope)"
        r"|\bscope\b[^\n]{0,80}(?:\*\.[a-z0-9-]+\.[a-z]{2,}|[a-z0-9-]+\.[a-z]{2,}[,/\s])"
        r"|this policy covers", re.I),
    "reward": re.compile(
        r"\breward|\bboun(?:ty|ties)\b|monetary|compensat|remunerat|\bswag\b"
        r"|hall of fame|acknowledg(?:e|ment)s? page|£\s?\d|€\s?\d|\$\s?\d", re.I),
    # Milestone B needs CASH. A "unique <brand> reward" is swag and must not read as paid.
    "monetary_reward": re.compile(
        r"£\s?\d|€\s?\d|\$\s?\d|monetary (?:reward|compensat)|cash (?:reward|prize)"
        r"|will be paid|financial reward", re.I),
    # One real policy says "You will not be paid a reward ... (known as a bug bounty)"
    # and was scoring reward=True. This clause has to win over the reward pattern.
    "no_reward": re.compile(
        r"(?:do|does|will) not (?:offer|provide|pay|be paid)[^.]{0,40}(?:reward|boun|compensat)"
        r"|not be (?:paid|eligible for)[^.]{0,30}(?:reward|boun)"
        r"|no (?:financial|monetary) reward|unable to (?:offer|provide)[^.]{0,30}reward"
        # a retired bounty reads as a live one unless "no longer" is caught: one policy
        # says "we no longer offer monetary rewards ... now a points-based programme"
        r"|no longer (?:offer|pay|provide|run)[^.]{0,40}(?:reward|boun|monetar)"
        r"|points[- ]only|points[- ]based (?:programme|program)", re.I),
    "platform": re.compile(r"hackerone|bugcrowd|synack|intigriti|yeswehack|openbugbounty", re.I),
    # ANTI-SIGNAL, safety critical. Some policies invite REPORTS while explicitly
    # withholding permission to TEST ("we do not authorize or encourage active testing,
    # scanning, or auditing of our systems"). That is a receiving address, not
    # authorisation, and under UK CMA 1990 the difference is the whole offence.
    # This must HARD-BLOCK the gate, never merely fail to raise it.
    "no_authorisation": re.compile(
        r"do(?:es)? not (?:authori[sz]e|permit|allow|condone)[^.]{0,60}"
        r"(?:test|scan|audit|research|probe)"
        r"|without (?:our )?(?:prior )?(?:express |written )+(?:consent|permission|authori)"
        r"|(?:testing|scanning) is (?:not permitted|prohibited|forbidden)", re.I),
    # ANTI-SIGNAL. Distinct from no_authorisation: manual research is welcome, but
    # TOOLING is not. This collides directly with our default method - console-batch
    # sends batched fetch() calls, which is automated traffic no matter how few.
    # Where this fires, hunt by hand or not at all.
    "no_automation": re.compile(
        r"(?:do not|don't|never) (?:run|use)[^.]{0,40}automated"
        r"|automated (?:scanning|tools|scanners)[^.]{0,30}(?:out of scope|prohibited|not permitted)"
        r"|avoid automated scanner|no automated (?:tool|scan)"
        r"|use of vulnerability assessment tools", re.I),
    # A programme that is not currently accepting reports is not a venue.
    "reports_paused": re.compile(
        r"paus(?:e|ing|ed)[^.]{0,40}(?:new )?reports?"
        r"|temporarily (?:closed|suspend|not accepting)"
        r"|not (?:currently )?accepting (?:new )?(?:reports?|submissions?)", re.I),
}

# GPT's correction, adopted: one boolean cannot express these. A policy can authorise
# research yet forbid tooling; pay yet refuse active testing; define scope yet be closed.
# The verdict is what we act on; the dimensions are why.
VERDICTS = {
    "BLOCKED":     "policy withholds permission to test - incidental discovery only",
    "PAUSED":      "not accepting reports right now - no venue",
    "MANUAL_ONLY": "authorised, but automated tooling is forbidden (no console-batch)",
    "HUNT":        "authorised, scoped, open, tooling not forbidden",
    "WEAK":        "no explicit safe harbour or no defined scope",
}


def strip_html(body):
    """Drop script/style/noscript FIRST - otherwise inline CSS and JS dominate the text
    and push the real policy prose past every budget."""
    body = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", body)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)).split())

_lock = threading.Lock()
_last = [0.0]


def throttle(rate):
    """Global rate limit shared across worker threads."""
    if rate <= 0:
        return
    gap = 1.0 / rate
    with _lock:
        wait = _last[0] + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()


def get(url, ua, timeout, rate, maxlen=200000):
    throttle(rate)
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(maxlen).decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except Exception as e:
        return 0, "{}: {}".format(type(e).__name__, e), url


def parse_security_txt(body):
    """RFC 9116: 'Field: value' lines. Multiple Contact/Policy lines are legal."""
    out = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip().lower(), v.strip()
        if k in FIELDS and v:
            out.setdefault(k, []).append(v)
    return out


def sweep_one(domain, args):
    rec = {"domain": domain, "security_txt": None, "fields": {}, "note": ""}
    for path in ("/.well-known/security.txt", "/security.txt"):
        code, body, final = get("https://" + domain + path, args.ua, args.timeout, args.rate)
        if code == 200 and body:
            # An HTML 200 is a catch-all route, not a security.txt.
            if "<html" in body[:400].lower():
                rec["note"] = "html at security.txt path (catch-all route)"
                continue
            rec["security_txt"] = final
            rec["fields"] = parse_security_txt(body)
            break
        if code == 0 and not rec["note"]:
            rec["note"] = body[:90]
    return rec


def score_policy(rec, args):
    urls = rec.get("fields", {}).get("policy") or []
    if not urls:
        return rec
    url = urls[0]
    if not url.lower().startswith(("http://", "https://")):
        return rec
    code, body, _ = get(url, args.ua, args.timeout, args.rate, maxlen=600000)
    rec["policy_status"] = code
    if code != 200 or not body:
        return rec
    apply_signals(rec, strip_html(body))
    return rec


def apply_signals(rec, text):
    """Score one policy page into independent dimensions, then a single verdict."""
    hits = {k: bool(p.search(text)) for k, p in SIGNALS.items()}
    if hits.pop("no_reward", False):
        hits["reward"] = False
        hits["monetary_reward"] = False
        rec["reward_explicitly_declined"] = True

    dims = {
        "scope_defined": hits["scope"],
        "safe_harbour": hits["safe_harbour"],
        "active_testing_allowed": not hits.pop("no_authorisation"),
        "automated_testing_allowed": not hits.pop("no_automation"),
        "reports_open": not hits.pop("reports_paused"),
        "monetary_reward": hits["monetary_reward"],
        "any_reward": hits["reward"],
        "platform_managed": hits["platform"],
        "intake": bool(rec.get("fields", {}).get("contact")),
    }
    rec["dimensions"] = dims
    rec["signals"] = hits  # kept for backwards compatibility with older runs

    # Order matters: a hard prohibition outranks everything a policy offers.
    if not dims["active_testing_allowed"]:
        v = "BLOCKED"
    elif not dims["reports_open"]:
        v = "PAUSED"
    elif not (dims["scope_defined"] and dims["safe_harbour"] and dims["intake"]):
        v = "WEAK"
    elif not dims["automated_testing_allowed"]:
        v = "MANUAL_ONLY"
    else:
        v = "HUNT"
    rec["verdict"] = v
    rec["gate_pass"] = v in ("HUNT", "MANUAL_ONLY")
    return rec


def score_url(url, args):
    """Score a policy page handed to us directly (e.g. a dork hit), skipping stage 1.
    Intake cannot come from security.txt here, so look for a contact ON the page."""
    from urllib.parse import urlparse
    rec = {"domain": urlparse(url).netloc, "security_txt": None,
           "fields": {}, "note": "direct policy URL", "policy_url": url}
    code, body, final = get(url, args.ua, args.timeout, args.rate, maxlen=600000)
    rec["policy_status"] = code
    if code != 200 or not body:
        return rec
    text = strip_html(body)
    rec["text_len"] = len(text)
    # Intake must be resolved BEFORE scoring - the verdict depends on it.
    mails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    forms = re.findall(r"(?i)(hackerone\.com|bugcrowd\.com|intigriti\.com|forms\.gle|/report)", body)
    intake = sorted(set(m for m in mails if not m.lower().endswith((".png", ".jpg"))))[:3]
    rec["fields"]["contact"] = intake or (["form: " + forms[0]] if forms else [])
    apply_signals(rec, text)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("domains", nargs="?", help="file with one domain per line")
    ap.add_argument("-o", "--out", default="vdp_sweep.jsonl")
    ap.add_argument("--policy", action="store_true", help="stage 2: fetch and score Policy: URLs")
    ap.add_argument("--rate", type=float, default=4.0, help="global requests/sec (default 4)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--contact", default="researcher", help="identity for the User-Agent")
    ap.add_argument("--report", metavar="JSONL", help="print a ranked table from a previous run")
    ap.add_argument("--urls", metavar="FILE",
                    help="score policy URLs directly (dork hits), one per line")
    args = ap.parse_args()
    args.ua = UA.format(c=args.contact)

    if args.report:
        report(args.report)
        return
    if args.urls:
        with open(args.urls, encoding="utf-8") as f:
            urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        with open(args.out, "w", encoding="utf-8") as out:
            for u in urls:
                rec = score_url(u, args)
                out.write(json.dumps(rec, ensure_ascii=False) + chr(10))
                out.flush()
        report(args.out)
        return
    if not args.domains:
        ap.error("need a domains file, --urls, or --report")

    with open(args.domains, encoding="utf-8") as f:
        domains = [l.strip().lstrip("*.").rstrip("/") for l in f
                   if l.strip() and not l.startswith("#")]
    domains = list(dict.fromkeys(domains))
    print("[*] {} domains, {} req/s, stage2={}".format(len(domains), args.rate, args.policy),
          file=sys.stderr)

    found = 0
    with open(args.out, "w", encoding="utf-8") as out, \
            ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, rec in enumerate(pool.map(lambda d: sweep_one(d, args), domains), 1):
            if rec["security_txt"]:
                found += 1
                if args.policy:
                    rec = score_policy(rec, args)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            if i % 25 == 0 or i == len(domains):
                print("    {}/{}  security.txt found: {}".format(i, len(domains), found),
                      file=sys.stderr)
    print("[+] {}/{} have security.txt -> {}".format(found, len(domains), args.out),
          file=sys.stderr)
    report(args.out)


ORDER = {"HUNT": 0, "MANUAL_ONLY": 1, "WEAK": 2, "PAUSED": 3, "BLOCKED": 4}


def report(path):
    rows, blocked_rows = [], []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        if not (r.get("security_txt") or r.get("policy_url")):
            continue
        d = r.get("dimensions", {})
        v = r.get("verdict", "-")
        if v == "BLOCKED":
            blocked_rows.append(r["domain"])
        rows.append((
            ORDER.get(v, 9), v, d.get("monetary_reward"), d.get("any_reward"),
            d.get("automated_testing_allowed", True), d.get("platform_managed"),
            r["domain"],
            (r.get("fields", {}).get("contact") or [""])[0][:34],
        ))
    # verdict first, then cash, then self-hosted before platform-managed
    rows.sort(key=lambda x: (x[0], not x[2], bool(x[5]), x[6]))
    print("\n{:<13}{:<6}{:<7}{:<7}{:<10}{:<30}{}".format(
        "VERDICT", "CASH", "REWARD", "AUTO", "MANAGED", "DOMAIN", "CONTACT"))
    print("-" * 122)
    for _, v, cash, rw, auto, pf, dom, c in rows:
        print("{:<13}{:<6}{:<7}{:<7}{:<10}{:<30}{}".format(
            v, "yes" if cash else ".", "yes" if rw else ".",
            "ok" if auto else "NO", "platform" if pf else ".", dom, c))

    counts = {}
    for row in rows:
        counts[row[1]] = counts.get(row[1], 0) + 1
    print("\n" + " . ".join("{}={}".format(k, counts[k]) for k in sorted(counts, key=lambda k: ORDER.get(k, 9))))
    if blocked_rows:
        print("\n!! BLOCKED - policy withholds permission to test. Incidental discovery and\n"
              "   reporting only, never active testing: " + ", ".join(blocked_rows))
    print("\nAUTO=NO means automated tooling is forbidden -> NO console-batch, hunt by hand.")
    print("Verdicts are regex triage, NOT permission. Read the policy before touching a host.")


if __name__ == "__main__":
    main()
