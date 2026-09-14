# UNAUTH RECON — the pre-credential runbook

**Born 2026-09-14 out of hunt #39.** That hunt produced the most complete
unauthenticated surface map we have ever built, and then the programme was disabled before a single
authenticated request was made. Everything below was earned with **no account, no credentials, and
no cooperation from the target.**

Run this **after §1 GATE and before lane selection**. It is the concrete expansion of
`HUNT_PROTOCOL.md` §3. The protocol says *what* must be enumerated; this says *how*, in order.

> **Why it matters beyond one hunt:** credentials arrive late, or never. On #39 they never arrived
> at all. A hunt that can only start after login is a hunt that can be killed by a support queue.

---

## 0 · GUARDS — restate every session, non-negotiable

- Required UA / marker header on **every** request, from the first one.
- **Never** a third party's identifier: no real login, IMEI, ICCID, account id, order id, token.
  The only foreign selector allowed is **belongs-to-nobody** (`pb0727`).
- **Never** invoke a destructive-sounding endpoint to test reachability. No method trick is provably
  safe — many frameworks route every verb to one handler. Mark it `UNTESTABLE — DESTRUCTIVE`.
- No scanners, no name-guessing at volume. If an enumeration needs guessing, record the remainder as
  `NOT TESTED — ROE`, never as "enforced".
- Anything that reaches real personal or payment data: **STOP and report.** No confirmation pass.
- **A programme can be disabled mid-hunt.** Authorisation is a live state, not a one-time grant.

---

## 1 · HOST FINGERPRINT — how many apps live here?

Do not assume one host = one app. #39 had **four** on a single in-scope hostname, each with its own
stack, session cookie and build.

- [ ] Fetch `/`, read response headers: `Server`, `X-Powered-By`, framework cache headers.
- [ ] Extract **every** internal link from the landing page and group by first path segment.
- [ ] For each distinct segment that smells like an app (`/account`, `/shop`, `/subscribe`…), fetch
      it and compare headers + `Set-Cookie` names. **Different session cookie = different app.**

⚠️ On #39 the subscriber app was found from a **footer link**, not from any manifest. Had that link
been absent, an entire application would have been missed while the notes said "fully enumerated".

---

## 2 · PER-APP BUNDLE PULL — the manifest is a SAMPLE (`pb0758`)

For each app, in this order. Skipping a step loses the route table.

- [ ] **Build manifest** (`_buildManifest.js` for Next pages router; equivalent elsewhere) → route
      list + per-route chunks.
- [ ] **Webpack runtime chunk map** — fetch `webpack-*.js`, parse `r.u = e => …`. This lists the
      **lazy** chunks no manifest mentions. On #39 this was **76 chunks across two apps**.
- [ ] **`_app` / `main` / `framework`** — from the page HTML, **not** the manifest, which never
      lists them. **Both route tables that mattered on #39 lived in `_app`.**
- [ ] App-Router apps ship no build manifest and may declare one lazy chunk. Their route total can be
      genuinely unknowable offline → record `N / ?`, never invent a denominator.

**Score on #39: 89 of 208 files (43%) were invisible to every manifest.**

### 2a · RECONCILE, LOUDLY (`pb0762`)
After every batch: for each expected item `test -s <file> || echo MISSING`, and print
`downloaded / expected / failed` as three numbers.

Three silent failures in one session, all reporting success:
- filenames containing `[...]` wrote **0 bytes** while curl printed `200` — twice;
- a text-mode write emitted CRLF, so every URL carried a trailing `\r` and 38 fetches returned curl
  code `000` — **which looks exactly like being IP-blocked.** One control request to a known-good URL
  disproved it in three seconds.

> **When a whole batch fails identically, send ONE control request before concluding you are
> blocked.** Identical failure across all legs is an instrument signature, not target behaviour.

---

## 3 · SERVER-SIDE ROUTE TABLES + RUNTIME CONFIG

- [ ] Grep the corpus for constant objects of `NAME: "/path"` and `NAME: \`${base}/path\`` — #39's
      `_app` held **97 endpoint constants**.
- [ ] Resolve every `${base}`. A base pointing at an **internal/RFC1918 address** means those
      endpoints are server-side only and **not a surface** — do not waste probes on them.
- [ ] Fetch the runtime config the app reads (`env-config.js`, `window._env_`, `publicRuntimeConfig`).
      **Check whether NON-public keys leak values.** #39's client code destructured
      `apiPassword`, `cmsToken`, `siApiKey` — and the served file carried only `PUBLIC_*`, so it was
      clean. Had it not been, that is a genuine, qualifying secrets finding.
- [ ] Secret-scan the whole corpus. A clean result needs a **filter-OFF control** before it can be
      called ENFORCED rather than PARTIAL.

---

## 4 · THE FREE CORPORA — one pull is a SAMPLE (`pb0759`)

- [ ] **Wayback CDX, TWO ways, then union**: the `limit=` form and the paginated `page=0..N` form.
      On #39 these were **disjoint slices** — pull 1 held 20 869 the other lacked, pull 2 held
      20 673, and **only pull 1 contained the entire `/api` tree.** Either alone gives a confident
      wrong answer *and* silently loses an endpoint family.
- [ ] ⚠️ `matchType=domain` **silently includes subdomains**, which are usually out of scope.
      **Filter to the exact in-scope hostname before counting anything.** On #39 that removed 2 314
      URLs and all of the junk that would have wasted hours.
- [ ] **urlscan.io** — paginate with `search_after` until a page returns 0.
- [ ] **Common Crawl** — the newest 2–3 indexes.
- [ ] `robots.txt` · `sitemap.xml` · `/plan-du-site`-style site maps · `/.well-known/*` ·
      `llms.txt` / `llms-full.txt` · source maps.
- [ ] **Declare convergence, don't assume it.** Enumeration is finished when a fresh source adds
      ~nothing. On #39 the site map offered 50 links of which **one** was unknown.

### 4a · WHAT TO MINE OUT OF THE CORPUS
- **Endpoint families** no manifest can list (`/api/*`, legacy `.php`/`.pl`/`.cgi`).
- **Selector shapes** — the authenticated URL patterns. #39 yielded
  `?doc=pdf&<line>&id=<hex>` (two selectors, one object) and a **base64 identity selector in a query
  string**. This is the split-brain-authz shape; write it down for the post-auth phase.
- **Query-parameter census** — rank by frequency. `redirect`, `url`, `goto`, `callback` are the
  open-redirect candidates; `id`, `user`, `*Id` are the object selectors.
- **🔑 JWT-shaped path segments and `token=` / `/reset/` URLs** (`pb0760`). #39 found **20
  password-reset tokens for 20 real subscribers**, spanning four years and reaching into the
  current month. Verify validity by decoding `exp` **OFFLINE**; never transmit the token. Treat them
  as third-party credentials: shape only, never values, never in a report.

---

## 5 · LIVE PROBES — every one needs a control in the same batch

- [ ] **Establish the 404 fingerprint first.** Probe a path that cannot exist and record its
      status + size + content-type. Without it, a 404 is unreadable.
- [ ] ⚠️ A catch-all route may return **200 for everything** — then status is a dead oracle and only
      content-type or body discriminates. Find this out with the control, not with a finding.
- [ ] Probe the `/api` tree found in §4. `200 + JSON` vs the 404 fingerprint = deployed vs not.
- [ ] Legacy handlers: still live, or redirected/410'd? On #39 the entire PHP/Perl estate 301'd to
      the modern apps — a large-looking surface, verdicted `N/A` in ten minutes.
- [ ] Feature-flagged routes: **a client flag set `false` does not undeploy the server route**
      (`pb0761`). Probe each one. On #39, 9 of 10 were genuinely disabled server-side — knowable only
      because a random sibling name returned something *different* from the real names.

---

## 6 · FRAMEWORK-SPECIFIC FREE WINS

### Next.js App Router — Server Actions (`pb0757`)
- [ ] Grep bundles for `createServerReference("<id>", …, "<functionName>")` — **the ids AND the
      function names ship publicly**.
- [ ] Invoke with `POST` + `Next-Action: <id>` + a JSON array body, against any route of that app.
      **No session, no CSRF token needed to reach them.**
- [ ] **Run a no-arg action FIRST as the instrument control.** Without it, a `false` from the real
      target is indistinguishable from a broken invocation.

> ⭐ **This is the single best trick from #39.** The open-redirect lane was recorded UNTESTABLE
> because the redirect only fires *after* login. But the allowlist check was exported as a server
> action — so the gate could be called **directly, unauthenticated**, 16 legs with 2 controls in one
> batch. **A client-side-only decision is still server-testable when the decision function is
> exported.**

### RSC / flight payloads
Reflections into `__NEXT_DATA__` or the RSC payload are **Next echoing the request URL**, not a
sink. Do not report them.

---

## 7 · CLASS COVERAGE REACHABLE WITHOUT AN ACCOUNT

| class | unauth-reachable? | how |
|---|---|---|
| CORS | **YES, fully** | N targets × Origins (absent / off-host / same-host / `null` / suffix-confusion) + OPTIONS preflight. ⚠️ **instrument control:** confirm your parser reads `Allow-Origin` from a known-CORS third-party host, or absence is unreadable |
| Open redirect | **often YES** | find the gate function (§6) and call it, or probe redirect-capable routes |
| Secrets / disclosure | **YES** | §3, and a filter-OFF control before claiming clean |
| SQLi / XSS / SSTI | **PARTIAL** | build the **input inventory first**, then ONE marker per field (§8) |
| Auth boundary | **YES** | probe every known authenticated route with no session — they must all refuse. ⚠️ this is the *anonymous→authenticated* boundary ONLY, not privilege separation |
| SSRF/XSPA | **sometimes N/A** | if the only free-text sink calls an **off-scope** host client-side, there is no in-scope sink. That is **N/A**, not "enforced" |
| BOLA · BFLA · mass-assignment · business logic | **NO** | structurally need two principals. Record the selector inventory from §4a and stop |

---

## 8 · THE INJECTION CANARY — inventory first, then one marker per field

- [ ] **Count the fields before testing any.** Query params + body fields + server-action arguments.
      A canary without a counted denominator is a spot-check wearing a verdict's clothes.
- [ ] ONE unique marker per field, carrying every interesting character at once:
      `zqcNN'"<>&{{7*7}}`. One request per field. **Never payloads × fields — that is scanning.**
- [ ] **Control:** a field known to reflect. Without it, "not reflected" is unreadable.
- [ ] Sort into `INTACT` / `TRANSFORMED (how)` / `not reflected`. Payloads later, on survivors only.

#39: **23 / 23 fields**, 3 reflected, all escaped, 0 raw, `{{7*7}}` literal everywhere.

---

## 9 · WRITE IT DOWN WHILE IT IS TRUE

- [ ] Matrix row updated **the moment** a verdict lands, with its denominator.
- [ ] ⚠️ **Re-read the HEADER BLOCK before every sync.** On #39 two files carried `filed 0` and
      `phase GATE` for hours after both were false, because only body sections were being patched.
- [ ] Any status copied from a memory file is a **CACHE, not a source.** Check the platform before
      asserting that a report is accepted, duplicate, paid or closed.

---

## 10 · WHEN THE HUNT DIES ANYWAY

A programme can be disabled, scope-reduced, or go silent at any moment. #39 ended by email.

**What survives a dead hunt, if this runbook was followed:** the technique entries, the framework
tricks, the instrument-failure lessons, and the retained `.js` corpus under the bundle carve-out.
**What dies:** every lane that was waiting on credentials.

> ⭐ **Therefore: do the unauth phase FIRST and do it completely.** It is the only part of a hunt
> that nobody can take away from you afterwards.
