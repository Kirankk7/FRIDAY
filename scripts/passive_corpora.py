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

ALLOWED_FETCH_HOSTS = ("web.archive.org", "urlscan.io")
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
    try:
        _u = ("https://web.archive.org/cdx/search/cdx?url=%s&matchType=domain"
              "&showNumPages=true") % urllib.parse.quote(host, safe="")
        npages = int(_get(_u).strip() or 0)
    except Exception as exc:
        print("    wayback showNumPages FAILED: %s" % exc)
    for p in range(min(npages, max_pages)):
        try:
            paged += _cdx(host, "page=%d" % p)
        except Exception as exc:
            print("    wayback page=%d FAILED: %s" % (p, exc))
            break
        time.sleep(0.4)
    forms["paged"] = paged
    forms["_npages"] = npages

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
    a = ap.parse_args()

    outdir = os.path.join(OUT_ROOT, a.target)
    os.makedirs(outdir, exist_ok=True)
    everything, per_host = {}, {}

    for host in a.host:
        print("\n=== %s" % host)
        wb, forms, dropped = wayback(host)
        print("    wayback  limit=%-6d paged=%-6d (%d cdx pages)  union=%-6d  off-host dropped=%d"
              % (forms.get("limit", 0), forms.get("paged", 0), forms.get("_npages", 0),
                 len(wb), dropped))
        print("             disjointness: only-in-limit=%d  only-in-paged=%d  <- pb0759 holds "
              "only if these are non-zero" % (forms.get("_only_limit", 0),
                                              forms.get("_only_paged", 0)))
        us, us_raw, us_drop, us_total, us_nourl = (
            ({}, 0, 0, 0, 0) if a.skip_urlscan else urlscan(host))
        if not a.skip_urlscan:
            print("    urlscan  api_total=%-6s pulled=%-5d exact-host=%-5d off-host=%-5d no-url=%d"
                  % (us_total, us_raw, len(us), us_drop, us_nourl))
        urls = set(wb) | set(us)
        print("    UNION    %d unique urls on this exact host" % len(urls))
        per_host[host] = {"wayback_limit": forms.get("limit", 0),
                          "wayback_paged": forms.get("paged", 0),
                          "wayback_union": len(wb), "off_host_dropped": dropped,
                          "urlscan_api_total": us_total, "urlscan_pulled": us_raw,
                          "urlscan_exact": len(us), "urlscan_off_host": us_drop,
                          "urlscan_no_url": us_nourl,
                          "union": len(urls)}
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
