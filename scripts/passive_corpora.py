#!/usr/bin/env python3
"""Pull the free off-target corpora for a host list: Wayback CDX (two forms, unioned) + urlscan.io.

Why this exists: the step was in the protocol and in UNAUTH_RECON, and no tool implemented it, so
on at least one hunt it sat in the matrix as "NOT MINED" while the hunt moved to lane selection.
A checklist item with no tool behind it is a checklist item that does not happen.

These are THIRD-PARTY archives, not the target. Nothing here sends a request to the programme's
own infrastructure, which is the entire point: it is the only enumeration nobody can withdraw.
Because of that, this tool deliberately does NOT go through core.net / scope_guard - that guard
holds the TARGET scope and would refuse archive.org. It carries its own two-host allowlist
instead, and will not fetch anything else.

Two lessons are wired in as behaviour, not comments:

  pb0759  One pull is a SAMPLE. The CDX `limit=` form and the paginated `page=` form returned
          DISJOINT slices on hunt #39 - 20869 URLs in one that the other lacked, and only one of
          them held the entire /api tree. Both are pulled and unioned, and the overlap is
          reported so a future reader can see whether that still holds.

  trap    `matchType=domain` silently includes SUBDOMAINS, which are usually out of scope. The
          exact-host filter runs before any count, and the number it removed is printed - on #39
          that was 2314 URLs of noise.

    python scripts/passive_corpora.py --target <name> --host a.example --host b.example
    python scripts/passive_corpora.py --target <name> --host a.example --skip-urlscan
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ALLOWED_FETCH_HOSTS = ("web.archive.org", "urlscan.io", "index.commoncrawl.org")
UA = "research-recon/1.0 (passive archive reads only)"
OUT_ROOT = "workspace/coverage"


def _get(url, timeout=60):
    """Fetch, but only from the two archive hosts. A narrow allowlist is the whole guard."""
    host = urllib.parse.urlparse(url).hostname or ""
    if host not in ALLOWED_FETCH_HOSTS:
        raise ValueError("refused: %s is not an archive host" % host)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ------------------------------------------------------------------ wayback
def _cdx(host, extra):
    base = ("https://web.archive.org/cdx/search/cdx?url=%s&matchType=domain"
            "&fl=original,mimetype,statuscode&collapse=urlkey&output=text&"
            % urllib.parse.quote(host, safe=""))
    txt = _get(base + extra)
    rows = []
    for ln in txt.splitlines():
        parts = ln.split(" ")
        if parts and parts[0].startswith("http"):
            rows.append((parts[0], parts[1] if len(parts) > 1 else "",
                         parts[2] if len(parts) > 2 else ""))
    return rows


def wayback(host, max_pages=12):
    """-> (union, by_form, filtered_out). Both CDX forms, unioned (pb0759)."""
    forms = {}
    try:
        forms["limit"] = _cdx(host, "limit=100000")
    except Exception as exc:
        forms["limit"] = []
        print("    wayback limit-form FAILED: %s" % exc)

    # The paginated form is a DIFFERENT index path, not the same query with an offset, which is
    # why it can return URLs the limit= form lacks (pb0759). It has to be driven properly:
    # ask showNumPages first, then walk 0..N-1. The first version guessed `page=N&pageSize=5`
    # and every page past 0 returned HTTP 400, so both "forms" were really the same pull and
    # the union was decorative.
    paged, npages = [], 0
    pages_ok, pages_fail = 0, 0
    try:
        _u = ("https://web.archive.org/cdx/search/cdx?url=%s&matchType=domain"
              "&showNumPages=true") % urllib.parse.quote(host, safe="")
        npages = int(_get(_u).strip() or 0)
    except Exception as exc:
        print("    wayback showNumPages FAILED: %s" % exc)
    # Page accounting, not a page count. "all N pages" is a COMPLETION claim and an artifact
    # that cannot show expected/attempted/successful/failed cannot make it. A run that walks
    # 219 of 227 pages successfully is PARTIAL, however useful the 219 were - and a failure
    # mid-walk must not end the walk, or every later page silently becomes "not attempted".
    for p in range(min(npages, max_pages)):
        try:
            paged += _cdx(host, "page=%d" % p)
            pages_ok += 1
        except Exception as exc:
            pages_fail += 1
            if pages_fail <= 3:
                print("    wayback page=%d FAILED: %s" % (p, str(exc)[:60]))
        time.sleep(0.4)
    forms["paged"] = paged
    forms["_npages"] = npages
    forms["_attempted"] = min(npages, max_pages)
    forms["_ok"] = pages_ok
    forms["_fail"] = pages_fail

    # the subdomain trap: matchType=domain pulls them in, and they are usually out of scope
    def exact(rows):
        keep, drop = [], 0
        for u, mime, code in rows:
            h = (urllib.parse.urlparse(u).hostname or "").lower()
            if h == host.lower():
                keep.append((u, mime, code))
            else:
                drop += 1
        return keep, drop

    f_exact, dropped = {}, 0
    for k, rows in forms.items():
        if k.startswith("_"):
            continue
        kept, d = exact(rows)
        f_exact[k] = kept
        dropped += d

    union = {}
    for k, rows in f_exact.items():
        for u, mime, code in rows:
            union.setdefault(u, (mime, code))
    meta = {k: len(v) for k, v in f_exact.items()}
    meta["_npages"] = forms.get("_npages", 0)
    meta["_pages_expected"] = forms.get("_npages", 0)
    meta["_pages_attempted"] = forms.get("_attempted", 0)
    meta["_pages_ok"] = forms.get("_ok", 0)
    meta["_pages_failed"] = forms.get("_fail", 0)
    meta["_complete"] = (forms.get("_npages", 0) > 0
                         and forms.get("_ok", 0) == forms.get("_npages", 0))
    meta["_only_limit"] = len(set(x[0] for x in f_exact.get("limit", []))
                               - set(x[0] for x in f_exact.get("paged", [])))
    meta["_only_paged"] = len(set(x[0] for x in f_exact.get("paged", []))
                               - set(x[0] for x in f_exact.get("limit", [])))
    return union, meta, dropped


# ------------------------------------------------------------------ urlscan
def urlscan(host, max_pages=20):
    """-> (kept, raw_seen, filtered_off_host, api_total).

    Returns FOUR numbers, not one. The first version returned only the filtered set, so when the
    exact-host filter removed everything it printed "0" - indistinguishable from the archive
    holding nothing. The control caught it: urlscan reports total=3026 for wikipedia.org and the
    tool said 0, because every result lives on a SUBDOMAIN and the filter is on the exact host.
    "None exist" and "all filtered" are different results and must never share a cell.
    """
    out, after, raw, dropped, nourl, dup, total = {}, None, 0, 0, 0, 0, None
    for _ in range(max_pages):
        q = "https://urlscan.io/api/v1/search/?q=%s&size=100" % urllib.parse.quote(
            'page.domain:"%s"' % host, safe="")
        if after:
            q += "&search_after=%s" % urllib.parse.quote(after, safe="")
        try:
            data = json.loads(_get(q))
        except Exception as exc:
            print("    urlscan FAILED: %s" % exc)
            break
        if total is None:
            total = data.get("total")
        res = data.get("results") or []
        if not res:
            break
        for r in res:
            raw += 1
            u = (r.get("page") or {}).get("url") or (r.get("task") or {}).get("url")
            h = (urllib.parse.urlparse(u or "").hostname or "").lower()
            if u and h == host.lower():
                if u in out:
                    dup += 1                      # urlscan holds many scans of one URL
                out[u] = r.get("_id", "")
            elif u:
                dropped += 1
            else:
                nourl += 1
        sort = res[-1].get("sort")
        if not sort:
            break
        after = ",".join(str(x) for x in sort)
        time.sleep(1.2)                                    # be a polite client
    # Invariant: every pulled record lands in exactly one bucket. The first version
    # had no third bucket, so 493 of 794 control records vanished between 'pulled'
    # and the two reported numbers. A count that does not reconcile is a defect
    # (pb0712), so this makes a wrong count loud rather than plausible.
    # urlscan returns one record per SCAN, so the same URL appears many times - 493 of 794 on
    # the control. Unique-kept is the useful number; the duplicates must still be accounted for
    # or the invariant fires on normal data and gets disabled, which is worse than no invariant.
    if len(out) + dup + dropped + nourl != raw:
        raise AssertionError("urlscan buckets do not reconcile: %d unique + %d dup + %d off-host "
                             "+ %d no-url != %d pulled"
                             % (len(out), dup, dropped, nourl, raw))
    return out, raw, dropped, total, nourl


# ------------------------------------------------------------------ common crawl
def _cc_indexes(n=3):
    """Newest n CC indexes. Fetched, never hardcoded - a pinned index silently goes stale and
    then reports 0 as though the corpus were empty."""
    try:
        data = json.loads(_get("https://index.commoncrawl.org/collinfo.json"))
    except Exception as exc:
        print("    commoncrawl collinfo FAILED: %s" % exc)
        return []
    return [d["id"] for d in data[:n] if d.get("id")]


def commoncrawl(host, n_idx=5, retries=2):
    """-> (kept, raw, dropped, idx_used, idx_tried). Exact-host filtered like every other leg.

    CC indexes 502 intermittently - probing five of them, two returned Bad Gateway while the
    other three answered the identical query. One failed index is NOT an empty corpus, so the
    caller gets BOTH numbers: how many indexes were tried and how many answered. A count drawn
    from 3 of 5 indexes is a sample and has to say so.
    """
    out, raw, dropped, dup = {}, 0, 0, 0
    used, tried = [], []
    for idx in _cc_indexes(n_idx):
        tried.append(idx)
        url = ("https://index.commoncrawl.org/%s-index?url=%s%%2F*&output=json"
               % (idx, urllib.parse.quote(host, safe="")))
        txt = None
        for attempt in range(retries + 1):
            try:
                txt = _get(url, timeout=120)
                break
            except Exception as exc:
                if attempt == retries:
                    print("    commoncrawl %s gave up: %s" % (idx, str(exc)[:55]))
                else:
                    time.sleep(2.5)
        if txt is None:
            continue
        used.append(idx)
        for ln in txt.splitlines():
            if not ln.strip().startswith("{"):
                continue
            try:
                rec = json.loads(ln)
            except Exception:
                continue
            raw += 1
            u = rec.get("url") or ""
            h = (urllib.parse.urlparse(u).hostname or "").lower()
            if u and h == host.lower():
                if u in out:
                    dup += 1              # CC lists one record per crawl capture
                out[u] = rec.get("mime", "")
            elif u:
                dropped += 1
            else:
                dup += 0
        time.sleep(0.8)
    # Same invariant as the urlscan leg: every record lands in exactly one bucket, or
    # the count is not a count. Found here as 555 records missing between raw and exact.
    if len(out) + dup + dropped != raw:
        raise AssertionError('commoncrawl buckets do not reconcile: %d unique + %d dup '
                             '+ %d off-host != %d raw'
                             % (len(out), dup, dropped, raw))
    return out, raw, dropped, used, tried


# ------------------------------------------------------------------ mining
_PARAM = re.compile(r"[?&]([A-Za-z0-9_.\[\]-]{1,40})=")
_JWTISH = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
_TOKENISH = re.compile(r"(?:token|reset|confirm|activate|verify|invite|key|signature)"
                       r"[=/][A-Za-z0-9._%-]{12,}", re.I)
_API = re.compile(r"/(api|v\d|graphql|rpc|rest|internal|admin|cp)(/|$)", re.I)
_LEGACY = re.compile(r"\.(php|pl|cgi|asp|aspx|jsp|do|action)(\?|$)", re.I)


def mine(urls):
    params, apis, legacy, tokens, jwts = {}, set(), set(), set(), set()
    for u in urls:
        path = urllib.parse.urlparse(u).path or "/"
        for p in _PARAM.findall(u):
            params[p] = params.get(p, 0) + 1
        if _API.search(path):
            apis.add(path)
        if _LEGACY.search(u):
            legacy.add(path)
        if _TOKENISH.search(u):
            tokens.add(u)
        if _JWTISH.search(u):
            jwts.add(u)
    return params, apis, legacy, tokens, jwts


REDIRECTISH = ("redirect", "redirect_uri", "redirecturl", "url", "goto", "next", "return",
               "return_to", "returnurl", "callback", "continue", "dest", "destination", "target")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--host", action="append", required=True)
    ap.add_argument("--skip-urlscan", action="store_true")
    ap.add_argument("--skip-cc", action="store_true")
    ap.add_argument("--cdx-pages", type=int, default=12,
                    help="CDX pages to walk; the default is a SAMPLE on big hosts")
    a = ap.parse_args()

    outdir = os.path.join(OUT_ROOT, a.target)
    os.makedirs(outdir, exist_ok=True)
    everything, per_host = {}, {}

    for host in a.host:
        print("\n=== %s" % host)
        wb, forms, dropped = wayback(host, max_pages=a.cdx_pages)
        print("    wayback  limit=%-6d paged=%-6d union=%-6d  off-host dropped=%d"
              % (forms.get("limit", 0), forms.get("paged", 0), len(wb), dropped))
        print("             cdx pages expected=%d attempted=%d ok=%d failed=%d  -> %s"
              % (forms.get("_pages_expected", 0), forms.get("_pages_attempted", 0),
                 forms.get("_pages_ok", 0), forms.get("_pages_failed", 0),
                 "COMPLETE" if forms.get("_complete") else "PARTIAL - this is a FLOOR"))
        print("             disjointness: only-in-limit=%d  only-in-paged=%d  <- pb0759 holds "
              "only if these are non-zero" % (forms.get("_only_limit", 0),
                                              forms.get("_only_paged", 0)))
        us, us_raw, us_drop, us_total, us_nourl = (
            ({}, 0, 0, 0, 0) if a.skip_urlscan else urlscan(host))
        if not a.skip_urlscan:
            print("    urlscan  api_total=%-6s pulled=%-5d exact-host=%-5d off-host=%-5d no-url=%d"
                  % (us_total, us_raw, len(us), us_drop, us_nourl))
        cc, cc_raw, cc_drop, cc_idx, cc_tried = (
            ({}, 0, 0, [], []) if a.skip_cc else commoncrawl(host))
        if not a.skip_cc:
            print("    commoncrawl indexes discovered=%d attempted=%d answered=%d failed=%d (%s)"
                  % (len(cc_tried), len(cc_tried), len(cc_idx), len(cc_tried) - len(cc_idx),
                     ",".join(i[-7:] for i in cc_idx) or "-"))
            print("                raw=%-6d exact-host=%-6d off-host=%-5d -> %s"
                  % (cc_raw, len(cc), cc_drop,
                     "COMPLETE" if cc_idx and len(cc_idx) == len(cc_tried)
                     else "PARTIAL - this is a FLOOR"))
        urls = set(wb) | set(us) | set(cc)
        print("    UNION    %d unique urls on this exact host" % len(urls))
        per_host[host] = {"wayback_complete": bool(forms.get("_complete")),
                          "cdx_pages_expected": forms.get("_pages_expected", 0),
                          "cdx_pages_attempted": forms.get("_pages_attempted", 0),
                          "cdx_pages_ok": forms.get("_pages_ok", 0),
                          "cdx_pages_failed": forms.get("_pages_failed", 0),
                          "wayback_limit": forms.get("limit", 0),
                          "wayback_paged": forms.get("paged", 0),
                          "wayback_union": len(wb), "off_host_dropped": dropped,
                          "urlscan_api_total": us_total, "urlscan_pulled": us_raw,
                          "urlscan_exact": len(us), "urlscan_off_host": us_drop,
                          "urlscan_no_url": us_nourl,
                          "cc_raw": cc_raw, "cc_exact": len(cc),
                          "cc_complete": bool(cc_idx and len(cc_idx) == len(cc_tried)),
                          "cc_indexes_answered": cc_idx, "cc_indexes_tried": cc_tried, "union": len(urls)}
        everything[host] = sorted(urls)

    allurls = sorted({u for v in everything.values() for u in v})
    params, apis, legacy, tokens, jwts = mine(allurls)

    json.dump({"target": a.target, "per_host": per_host, "urls": everything},
              io.open(os.path.join(outdir, "passive_corpora.json"), "w", encoding="utf-8"),
              indent=1)

    print("\n================ MINED  (%d urls across %d host(s))" % (len(allurls), len(a.host)))
    print("  API-shaped paths     : %d" % len(apis))
    print("  legacy ext paths     : %d" % len(legacy))
    print("  token/reset-ish urls : %d   <- decode exp OFFLINE, never transmit" % len(tokens))
    print("  JWT-shaped urls      : %d" % len(jwts))
    print("  distinct query params: %d" % len(params))
    red = [(p, n) for p, n in params.items() if p.lower() in REDIRECTISH]
    sel = [(p, n) for p, n in params.items()
           if re.fullmatch(r"(id|uid|user|userid|account|accountid|store|storeid|org|orgid"
                           r"|[a-z]+Id)", p, re.I)]
    if red:
        print("  redirect candidates  : %s" % ", ".join("%s(%d)" % x for x in sorted(red, key=lambda x: -x[1])))
    if sel:
        print("  object selectors     : %s" % ", ".join("%s(%d)" % x for x in sorted(sel, key=lambda x: -x[1])[:12]))
    if apis:
        print("\n  top API-shaped paths:")
        for p in sorted(apis)[:25]:
            print("    %s" % p[:110])
    print("\n  wrote %s" % os.path.join(outdir, "passive_corpora.json"))
    print("  NOT MINED by this tool: Common Crawl, source maps, GitHub code search, "
          "mobile artefacts, robots/sitemap. State them next to any count from this run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
