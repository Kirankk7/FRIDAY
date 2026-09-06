"""Unified Route Inventory — one normalized, deduped route store that every discovery SOURCE
fans into and every oracle (idor_check / auth_matrix / injection) fans out of.

The 2026-07-15 fleet battery proved detection is strong once handed URLs; the bottleneck is SEEING
the surface (hunt_lessons/2026-07-15-fleet-battery.md). The sources already exist but were siloed:
crawl (katana/crawl_site), SPA XHR (spa_crawl), OpenAPI (core/openapi), Burp history (core/burp_ingest),
JS endpoints (core/secrets.find_endpoints), and now HAR. This module unifies them: same route seen by
three sources = one entry with merged params + provenance. Deterministic, no network — pure aggregation.
Authorized targets only (the caller enforces scope).

SERVICE / GATE / SELECTOR LAYER (2026-09-06)
  A URL list answers "what exists". It does not answer the question hunt #37 actually turned on:
  which authorization gate does this route sit behind, and WHAT DOES NOT CROSS THAT GATE.

  pb0726 — authorization boundary discontinuity: once a shared gate is proven enforced, stop
  re-testing it and start enumerating everything that does NOT traverse it. Cross-tenant authz on
  ClearTax was proven on a shared interceptor; the finding that paid (report #16993) was on a route
  that never went through it. There was nowhere in this store to record that, so the pivot was made
  by hand and only after ~500 requests.

  Three fields carry it now:
    service    which backend answers this route (defaults to the host; set explicitly when one host
               fronts several, e.g. /graphql vs /graphql/docsvc/)
    gate       the NAME of the authorization check the route traverses, as PROVEN — never guessed
    selectors  the object-identifying arguments the route carries (entityId, workspaceId, scope…)

  ⚠️ `gate=None` means NOT DETERMINED. It never means ungated. `discontinuity()` keeps those two
  apart on purpose: "differs from the proven gate" is a lead, "never determined" is an unmeasured
  hole, and collapsing them is how a class gets marked green while untested.
"""
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_ID_SEG = re.compile(r"/(\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(/|$)", re.I)

# Templated path segments: /users/{userId}/  ·  /users/:userId/  ·  /users/<userId>/
_TEMPLATE_SEG = re.compile(r"[{<:]([A-Za-z_][A-Za-z0-9_]*)[}>]?(?=/|$)")

# Parameter names that identify an OBJECT rather than shape a query. These are the arguments a
# cross-tenant probe swaps; a route carrying one is a candidate the moment its gate is unknown.
_SELECTOR_NAME = re.compile(
    r"^(?:id|uuid|guid|slug|key|ref|scope|tenant|realm|owner)$"
    r"|(?:^|_|\b)(?:id|ids|uid|uuid|guid|index|idx|key|sid|arn|urn)$"
    r"|(?:id|Id|ID|Index|Uuid|UUID|Guid|Key|Sid)$"
    r"|^(?:tenant|workspace|account|entity|org|organisation|organization|project|customer|user|"
    r"member|company|team|group|document|file|invoice|order|payment|subscription)",
    re.I)


def is_selector(name):
    """True when a parameter name identifies an object (a thing a cross-tenant probe would swap)."""
    return bool(name) and bool(_SELECTOR_NAME.search(name))


class RouteInventory:
    def __init__(self):
        self._routes = {}   # (METHOD, scheme, netloc, path) -> route dict

    def add(self, url, method="GET", params=None, source="", auth=None, content_type="",
            service=None, gate=None, selectors=None):
        """Record one route. `service`/`gate`/`selectors` are optional and merge like the rest.

        `gate` must be a check you have PROVEN this route traverses — leave it None otherwise, and
        the route stays counted as unmeasured rather than silently assumed safe.
        """
        try:
            p = urlsplit(url.strip())
        except Exception:
            return self
        if p.scheme not in ("http", "https") or not p.netloc:
            return self
        method = (method or "GET").upper()
        path = p.path.rstrip("/") or "/"
        qp = {k for k, _ in parse_qsl(p.query, keep_blank_values=True)}
        qp |= set(params or [])
        sel = set(selectors or []) | self._infer_selectors(p.path, qp)
        key = (method, p.scheme, p.netloc, path)
        r = self._routes.get(key)
        if r is None:
            self._routes[key] = {
                "method": method, "url": urlunsplit((p.scheme, p.netloc, p.path, "", "")),
                "path": p.path, "params": set(qp),
                "sources": {source} if source else set(),
                "auth": auth, "content_type": content_type,
                "service": service or p.netloc, "gate": gate, "selectors": sel,
            }
        else:
            r["params"] |= qp
            r["selectors"] |= sel
            if source:
                r["sources"].add(source)
            if auth is not None:
                r["auth"] = auth
            if content_type:
                r["content_type"] = content_type
            if service:
                r["service"] = service
            if gate is not None:
                r["gate"] = gate
        return self

    @staticmethod
    def _infer_selectors(path, params):
        """Selector names visible without any extra knowledge: templated path segments plus
        object-identifying query parameters. A CONCRETE id segment (/users/1024/) is deliberately not
        named — we know a selector is there, not what the server calls it."""
        out = {m.group(1) for m in _TEMPLATE_SEG.finditer(path or "")}
        out |= {p for p in (params or set()) if is_selector(p)}
        return out

    def add_many(self, urls, **kw):
        for u in urls or []:
            self.add(u, **kw)
        return self

    def routes(self):
        return list(self._routes.values())

    def urls(self, params_only=False):
        """Representative URLs for the oracles. A route with params gets a query string (seeded '1')
        so the injection/idor probes have something to mutate."""
        out = []
        for r in self._routes.values():
            u = r["url"]
            if r["params"]:
                u = u + "?" + urlencode({k: "1" for k in sorted(r["params"])})
            elif params_only:
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def id_bearing(self):
        """URLs whose path carries a numeric/uuid segment — BOLA candidates for idor_check/auth_matrix."""
        return [r["url"] for r in self._routes.values() if _ID_SEG.search(r["path"])]

    # -------------------------------------------------------------- service / gate layer ----

    def mark_gate(self, gate, host=None, path_prefix=None, service=None, method=None,
                  allow_cross_service=False):
        """Tag every matching route as traversing `gate`. Returns how many routes were tagged.

        Call this ONLY after proving the gate on that surface with a passing control. This is a
        record of evidence, not a hypothesis — everything downstream treats a named gate as settled.

        🚨 Refuses to span services. A prefix match is a STRING match, and a nested service shares
        the prefix of the one it hangs off: tagging ClearTax's `/graphql` this way also swallowed
        `/graphql/docsvc/`, which is the one route that did NOT honour that gate (report #16985).
        Proof on one service is not evidence about another, so spanning two must be said out loud —
        pass `allow_cross_service=True` only when the gate really was proven on each of them.
        """
        matched = []
        for r in self._routes.values():
            if host and urlsplit(r["url"]).netloc != host:
                continue
            if service and r["service"] != service:
                continue
            if method and r["method"] != method.upper():
                continue
            if path_prefix and not r["path"].startswith(path_prefix):
                continue
            matched.append(r)
        spanned = sorted({r["service"] for r in matched})
        if len(spanned) > 1 and not allow_cross_service:
            raise ValueError(
                "mark_gate('%s') would span %d services: %s. A gate proven on one service is not "
                "evidence about another - narrow with service=, or pass allow_cross_service=True "
                "if it was genuinely proven on each." % (gate, len(spanned), ", ".join(spanned)))
        for r in matched:
            r["gate"] = gate
        return len(matched)

    def set_service(self, service, host=None, path_prefix=None):
        """Split one host into several backends — the shape behind ClearTax's `/graphql` vs
        `/graphql/docsvc/`, where the second answered to a different authorization model."""
        n = 0
        for r in self._routes.values():
            if host and urlsplit(r["url"]).netloc != host:
                continue
            if path_prefix and not r["path"].startswith(path_prefix):
                continue
            r["service"] = service
            n += 1
        return n

    def services(self):
        """{service: {routes, gates, ungated_unknown, selectors, hosts}} — the surface, grouped the
        way an authorization model is actually organised."""
        out = {}
        for r in self._routes.values():
            s = out.setdefault(r["service"], {"routes": 0, "gates": set(), "gate_unknown": 0,
                                              "selectors": set(), "hosts": set()})
            s["routes"] += 1
            s["hosts"].add(urlsplit(r["url"]).netloc)
            s["selectors"] |= r["selectors"]
            if r["gate"] is None:
                s["gate_unknown"] += 1
            else:
                s["gates"].add(r["gate"])
        return out

    def discontinuity(self, proven_gate):
        """pb0726 — given a gate PROVEN enforced, return everything that does not demonstrably
        traverse it. The pivot, not another pass at the gate you already closed.

        {
          "proven_gate":   the gate name you passed in,
          "traverses":     routes behind it — STOP TESTING THESE for that boundary,
          "gate_differs":  routes proven to sit behind a DIFFERENT gate — the lead,
          "gate_unknown":  routes whose gate was never determined — UNMEASURED, not ungated,
          "denominator":   total routes in the store,
        }

        Ranking inside each bucket: routes carrying selectors first, since a boundary is only
        crossable where there is an argument to swap.
        """
        traverses, differs, unknown = [], [], []
        for r in self._routes.values():
            if r["gate"] == proven_gate:
                traverses.append(r)
            elif r["gate"] is None:
                unknown.append(r)
            else:
                differs.append(r)

        def rank(rows):
            return sorted(rows, key=lambda r: (-len(r["selectors"]), r["service"], r["path"]))

        return {"proven_gate": proven_gate,
                "traverses": rank(traverses),
                "gate_differs": rank(differs),
                "gate_unknown": rank(unknown),
                "denominator": len(self._routes)}

    def matrix_rows(self, proven_gate=None):
        """Lines for `workspace/coverage/<target>_matrix.md`. Every row states its denominator, and
        an undetermined gate prints as NOT TESTED rather than disappearing."""
        d = self.discontinuity(proven_gate) if proven_gate else None
        lines = ["| service | hosts | routes | gates proven | gate unknown | selectors |",
                 "|---|---|---|---|---|---|"]
        for name, s in sorted(self.services().items()):
            lines.append("| %s | %s | %d | %s | %d/%d | %s |"
                         % (name, ", ".join(sorted(s["hosts"])), s["routes"],
                            ", ".join(sorted(s["gates"])) or "NOT TESTED",
                            s["gate_unknown"], s["routes"],
                            ", ".join(sorted(s["selectors"])[:6]) or "-"))
        if d:
            lines += ["",
                      "**Discontinuity vs `%s`** (denominator %d): %d traverse it (closed), "
                      "%d sit behind a different gate (LEAD), %d never determined (NOT TESTED — "
                      "not 'ungated')."
                      % (d["proven_gate"], d["denominator"], len(d["traverses"]),
                         len(d["gate_differs"]), len(d["gate_unknown"]))]
        return lines

    def summary(self):
        from collections import Counter
        c = Counter(s for r in self._routes.values() for s in r["sources"])
        gate_unknown = sum(1 for r in self._routes.values() if r["gate"] is None)
        return {"total": len(self._routes), "by_source": dict(c),
                "services": len({r["service"] for r in self._routes.values()}),
                "gate_unknown": gate_unknown,
                "with_selectors": sum(1 for r in self._routes.values() if r["selectors"])}


def from_har(path):
    """Parse a Chrome/Firefox HAR export (File > network.har) into {url, method, content_type} records.
    One click in DevTools captures every real request the browser made — richer than any crawl."""
    import json
    try:
        with open(path, "r", encoding="utf-8") as f:
            har = json.load(f)
    except Exception as e:
        return []
    out = []
    for e in (har.get("log", {}) or {}).get("entries", []) or []:
        req = e.get("request", {}) or {}
        url = req.get("url", "")
        if not url:
            continue
        ct = ""
        for h in req.get("headers", []) or []:
            if (h.get("name", "") or "").lower() == "content-type":
                ct = h.get("value", ""); break
        out.append({"url": url, "method": req.get("method", "GET"), "content_type": ct})
    return out
