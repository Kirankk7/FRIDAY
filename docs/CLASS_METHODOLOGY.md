# THE 17 ROWS — what we test, and how

Canonical list: `core/sweep.py::_CLASSES` (11) + `_MICRO` (6). Every hunt must carry a verdict with
a reason for all 17 before the word *closed* may be used (`HUNT_PROTOCOL` §3.5, §5).

⚠️ **11 classes since 2026-09-06, not 10.** RCE was split out of the old
`10. cmd/SSTI/XXE/path` because a parser boundary and a filesystem selector are not code execution,
and sharing one row let the highest-impact class inherit a verdict earned elsewhere. **Matrices
written before that date state `N/10` against the OLD taxonomy — never silently re-read them as
`N/11`.**

Verdict vocabulary is fixed and closed: `ENFORCED` · `FALSIFIED` · `UNTESTABLE` · `UNREADABLE` ·
`N/A` · `NOT TESTED`. Untestable never becomes safe.

---

## The method that applies to all 17

```
1  RECON        enumerate the surface OFFLINE first - bundles, schema, archives, docs.
                A count is not a denominator: state covered-vs-known or say it is unfinished.
2  CANDIDATES   let the shape of the request nominate the class, not a feeling.
3  CONTROL      every probe ships a positive control in the SAME batch.
                TARGET-side: an object we own, same code path, MUST succeed.
                INSTRUMENT-side: a fixture with known markers the extractor MUST recover.
4  PROBE        one variable at a time. Canary pass before payload pass.
5  VERDICT      from a SEPARATE state read, never from the write's own response.
6  DENOMINATOR  N tested of M known, per category, breadth AND flow transitions.
```

**Five rules that outrank class-specific technique**

| rule | earned from |
|---|---|
| Control fails ⇒ **UNREADABLE**. No verdict in either direction. | 4 bad verdicts in one hunt |
| An echoed field is what the server **claims**. Only a separate read shows what it **did**. | a wrong `ENFORCED` reached the matrix and the mirror |
| Absence from a **projection** is not absence from state. | told the operator a write failed when it had persisted |
| Different failure modes locate the gate; two identical refusals are the weakest evidence. | `pb0618` |
| Never a third party's data or identifier. Own objects, or belongs-to-nobody. | `pb0727` |

---

## 1. BOLA / IDOR
**Detector:** owner-scoped endpoint carrying an object id — an ownership boundary to cross.
**Method:** two principals, two distinguishing strings, so a response must name its own owner.
Probe every selector *family*, not every endpoint: path id, body id, query id, referer-carried id,
and the raw-UUID variant of each. When the shared gate is PROVEN, **stop** and pivot to what does
not traverse it (`pb0726` authorization boundary discontinuity).
**Verdict needs:** own → real data · foreign → refusal · no-session → a third, different outcome.
**Trap:** a refusal for an object that does not exist proves nothing. Make the foreign object real
(ours, second tenant) or the test is about nonexistence.

## 2. BFLA / privilege escalation
**Detector:** privileged path, or a state-changing method on a shared resource.
**Method:** enumerate the permission model first — an ACL oracle beats guessing. Then: can a lower
role invoke the higher role's function, and **can it disable the control that stops it?**
**Verdict needs:** a second principal. One account cannot demonstrate privilege separation.
**Trap:** RBAC is a paid feature on most SaaS. On the free tier the denominator is *0 of 1 role* and
the honest verdict is `UNTESTABLE — TIER`, not enforced. Hit on 3 of the last 6 hunts.

## 3. SQLi / NoSQLi
**Method:** error-based across **every** string field (not a spot-check), then time-based with
baselines either side. Pull raw error **strings**, never status codes.
**Verdict needs:** for FALSIFIED — no error, no 500, no differential, *and* no delay.
**Trap:** 11 of 17 query surfaces returning 404 because they need an id we cannot get is
`UNTESTABLE`, not clean. A quote stored untouched with no error is one field, not a class.

## 4. XSS — reflected + stored
**Detector:** reflection = a param echoed back; stored = text written now, rendered to someone later.
**Method:** input inventory **first** — mine write bodies for every string field. Canary pass
(one unique marker per field) sorted STORED-INTACT / TRANSFORMED / REJECTED, payloads only on the
survivors. Then the part almost everyone skips: **identify which field actually renders** before
injecting, and run an **execution** oracle, not a reflection check.
**Verdict needs:** `scripts/xss_oracle_check.py` passing **both** legs — raw reflection confirms,
escaped does not. An oracle with only a positive leg can say yes and never no.
**Traps:** (a) a marker that survives the encoding you are testing for cannot detect that encoding's
absence — an alphanumeric canary survived percent-encoding and produced a false positive.
(b) `<textarea>` content is RCDATA: tags never parse there whatever the encoding, so a textarea hit
proves nothing — only a `</textarea>` breakout does. (c) a strict CSP can make execution impossible
where reflection exists; read the header or the negative is about policy, not escaping.

## 5. SSRF / XSPA
**Detector:** a param the **server** dereferences — the class most often missed.
**Method:** classify the destination: user-supplied vs vendor-fixed. Then the validator shape —
a literal internal IP may 400 while the *same address as a resolving hostname* 201s, and delivery
dials it. Verdict on timing and on the callback, never on the body.
**Verdict needs:** an internet-reachable OAST listener, self-tested FIRST (`core/oast.py` never
falls back to loopback). No listener ⇒ `UNREADABLE` even if the lane is reachable.
**Traps:** the control must use the target's **own HTTP method** (`pb0618`); a never-resolvable
hostname is the strongest control there is; DNS-only SSRF is on the never-submit list alone.

## 6. Mass assignment
**Method:** touch ONE control in the UI, read the request, then ask **what else the body accepts**.
Canary each field, verify by a **separate state read**. Rank by privilege semantics: `force*`
prefixes, `approved`, plan/tier flags, numeric limits, foreign-tenant selectors.
**Verdict needs:** persistence **and** effect. "The write stuck" is not "the entitlement moved" —
the reportable bar is two server-side sources contradicting each other for the same object.
**Trap:** discarded-and-echoed. The write response returned the server's own value and I recorded
`ENFORCED`; a later read showed the field had persisted. **Verdict from the read, always.**

## 7. Business logic
**Method:** no signature to grep. Find the invariant the UI enforces and ask whether the server
does. Replay the **commit** step. Race the single-use. Re-read a limit the client computed.
**Verdict needs:** impact on state, with the server's own oracle contradicting itself where possible.
**Trap:** races are excluded by name on several programmes — check before spending hours. And the
flow may live on an **ineligible asset**, which is `OUT_OF_SCOPE`, not a finding.

## 8. Secrets / disclosure
**Method:** scan the whole corpus — minified bundles, **source maps** (`sourcesContent` gives
unminified originals), archived bundles from Wayback, and the server-rendered hydration payload.
**Verdict needs:** a **filter-OFF control** before clean counts as anything. A scan reporting zero
with nothing proving it can see a secret is not a result.
**Trap:** two pattern tables existed in our own code (15 legacy vs 150 live) and the wrong one was
being called. Also: source-map exposure alone is non-qualifying on most programmes.

## 9. Auth / session
**Method:** per component, not per app — token mint, token verify, expiry, burn/one-use, device
binding, password/reset flow, SSO assertion, tenant binding. Each needs its own control.
**Verdict needs:** distinct failure modes per leg. Identical refusals across legs mean you have
found one check, not four.
**Trap:** phishing and social engineering are prohibited by name — that is `NOT TESTED BY CHOICE`
with the rule quoted, never a gap.

## 10. RCE / server-side execution — **its own class since 2026-09-06**
**Method:** build the sink inventory FIRST (`core/sink_inventory.py`, 10 interpreter kinds, every
one starts **NOT SEARCHED**). Then the safe-PoC ladder:

```
L0  identify the sink          no payload
L1  reach it benignly          does input change the INTERPRETER's behaviour?
                               timing shift, parser error that MOVES with input, {{7*7}} -> 49
L2  OAST callback              a DNS/HTTP hit IS execution evidence for a blind sink
L3  identity only, if named    id / whoami - ONLY when the brief names them in writing
STOP                           no shell, no write, no real file read, no persistence
```
**Trap:** without a sink list, "no sink identified" is a search, not a verdict — and the
highest-impact class gets closed on a feeling. One brief granted `id` and `whoami` **in writing**
and three surfaces went unprobed.

## 11. XXE / path traversal / LFI
**Detector:** parser and filesystem boundaries.
**Method:** find where the file is *parsed*, not where it is uploaded. Establish whether the parser
runs server-side at all — if import parsers are lazy-loaded into the browser, there is **no
server-side sink** and the class is `N/A` with that reason stated.
**Trap:** no YAML/XML bombs. DoS is forbidden by name on every programme we hunt.

---

## MICRO-CLASSES

| # | class | method | the trap |
|---|---|---|---|
| **JWT** | decode offline; check `alg`, lifetime, claim-to-identity binding, signature validation | signature validation is usually `UNTESTABLE` from outside — say so rather than implying strength |
| **CORS** | every in-scope host × every Origin shape × `{GET, OPTIONS}` | the instrument needs its own control; prove the parser read *something* on every leg, or 36 clean legs mean nothing |
| **CSRF** | token presence, rotation, and whether the server actually requires it | scope the claim to the product tested. Two apps, two token names, one assumption = the same mistake twice |
| **GraphQL abuse** | introspection · array batching · aliasing · query depth · field suggestions | "introspection disabled" is one check of five. Depth is the one we keep leaving at NOT TESTED |
| **Open redirect** | allowlist shape, and whether a rejected value still *suppresses* a mint | an allowlist named in an error message with a failing control is `UNREADABLE`, not enforced |
| **File upload** | type/extension/magic-byte checks, storage path, and whether the stored file is *served* | an upload that works on an empty store may be gated by state, not by policy |

---

## WHAT COMES BEFORE THE CLASSES

Recon order is fixed, and lane selection comes last:

```
gate -> authorised capture -> surface enumeration -> lane selection
```

- **Gate:** exact asset list counted **by type** (one scope was 31 assets, 20 of them mobile apps
  hitting the same API — we tested the web client and never wrote down the two thirds we skipped).
  Rules verbatim, pay cliff, ineligibility, safe harbour.
- **Unauth first and completely** (`docs/UNAUTH_RECON.md`) — it is the only part of a hunt nobody
  can withdraw afterwards. One programme was disabled mid-hunt before a single authenticated request.
- **Four inventories, not one:** routes · selectors+gates · sinks · schema.
- **Passive corpora** (`scripts/passive_corpora.py`): Wayback CDX **two forms unioned** — on one
  host the `limit=` form held 17% of the corpus and the paginated form held 504,309 URLs it lacked
  — plus urlscan, Common Crawl, source maps, GitHub code search. Every leg reports
  expected/attempted/succeeded/failed and derives COMPLETE vs PARTIAL; a partial run's counts are
  **floors** and may not become matrix denominators.
- **Bundles are the denominator, captures are the discovery.** Clicking the UI covers ~10%. Every
  bug we have filed came from a capture; the sweep tells you what the capture missed.
