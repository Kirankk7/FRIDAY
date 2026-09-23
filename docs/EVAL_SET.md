# EVAL_SET — failure signatures, drawn only from failures that ACTUALLY happened

**v1.1, 2026-09-06. 34 cases (31 + I-07b + I-15 + I-16), all from hunt #37 unless noted.**

## what this is, and what it is NOT
A **recognition checklist and a post-hunt audit**. Not a benchmark.

🚫 **I do not score myself on it before a hunt.** I wrote it, I have seen the answer key, and a
self-graded eval on memorised cases is theatre — the same defect [[lens-run-every-hunt]] names when
it says *the assistant cannot be the cold context*. A number produced that way measures recall, not
judgement.

✅ **Two legitimate uses:**
1. **During a hunt** — when an output matches a GIVEN shape, apply the GOOD reading before verdicting.
2. **At hunt close** — walk every case and, for each one that FIRED, write the forensic record
   below. **No ratio, no percentage** — the useful output is *which* failures recurred and *who*
   caught them, which is what tells you whether a protocol change or a subsystem is warranted.

**Growth rule: add a case ONLY when a real failure occurs. Never invent one.** A synthetic case
teaches my current opinion, including the wrong parts. If hunt #38 produces no new failure this file
does not grow — that is the good outcome, not a missed one.

---

## 1 · INSTRUMENT — my own tooling produced a confident wrong reading

### I-01 · zero findings beside mass unreadability
- **GIVEN** a sweep reports `swept 122 | ENFORCED 13 | FALSIFIED 0 | UNREADABLE 109`
- **BAD** "clean sweep, no cross-tenant defect"
- **GOOD** `FALSIFIED 0` next to `UNREADABLE 109` is a **broken instrument**, not a hardened target.
  Check the CONTROL leg before reading any test leg.
- **WHY** 109 were unreadable because my generated docs omitted selection sets on object-returning
  mutations. The target was never measured.

### I-02 · row COUNT used as an oracle
- **GIVEN** own id → 1 row · foreign id → 1 row · nonexistent id → 1 row
- **BAD** "returns rows for foreign ids ⇒ possible IDOR"
- **GOOD** an identical count for an id belonging to NOBODY means a synthesised stub.
  **Count is not an oracle; content is.**
- **WHY** all three carried `status: UN_AUTHORIZED_ACCESS` with empty fields.

### I-03 · response truncated before the part that answers the probe
- **GIVEN** an endpoint returns the WHOLE conversation; I print the first 700 chars
- **BAD** reading exchange #1 as the answer to the newest message
- **GOOD** parse and print the LAST element, the echoed user text, and the array length.
- **WHY** four prompt-injection probes all "returned" the same benign answer from message #1.

### I-04 · probe run against the wrong object
- **GIVEN** a DOM search finds nothing and reports "escaped"
- **BAD** "0 elements ⇒ escaped ⇒ ENFORCED"
- **GOOD** assert the payload is PRESENT first — absent ≠ safe. Print `location.pathname`; the app's
  own route carried both selectors (`/filing/<ay>/<entityIndex>/<entityId>/`) the entire time.
- **WHY** payload written to entity idx0, browser on entity idx2. Three rounds lost.

### I-05 · out-of-band listener not proven live
- **GIVEN** a callback URL was sent; the listener shows nothing
- **BAD** "no callback ⇒ no SSRF"
- **GOOD** fire a SELF-TEST first. Silence from an unproven listener is UNREADABLE, and live tails
  are not retroactive.
- **WHY** the first no-hit was a tail that had not been started.

### I-06 · payload destroyed before it could fire
- **GIVEN** a blind command-injection filename returns no callback
- **BAD** "no command injection"
- **GOOD** print the STORED value. Basename stripping had reduced `https://host/path` to `path`, so
  the callback never survived. Verify the payload is intact IN STORAGE before trusting silence.
- **WHY** slash-free callbacks stored verbatim; only then was the negative real.

### I-07 · an extractor whose output is a COUNT, with no invariant
- **GIVEN** a schema parser reports 374 mutations
- **BAD** quoting the number
- **GOOD** any extractor whose output is a count needs a self-check that makes a wrong count LOUD.
  Confirm `self-check: clean` before quoting.
- **WHY** the true value was 219; arguments were being promoted to sibling fields, silently.

### I-07b · a component silently blind to a schema its corpus grew
- **GIVEN** a retriever, extractor or harness returns a thin/empty/clean result and does not error
- **BAD** reading the silence as a fact about the DATA
- **GOOD** ask what the component can REPRESENT before asking what it found. Query it with text you
  KNOW is present; if that does not come back, the silence was about the reader, not the corpus.
- **WHY** `playbook.recall()` built its haystack from `class+stack+technique+payload`. Entries
  distilled after hunt #37 carry `title`/`tell`/`why` instead, so 19 of them (pb0726..pb0744 — the
  newest and most validated material) scored on nothing but their class and never surfaced, and the
  other 725 were matched on a fraction of their text. Querying pb0726's own subject returned five
  unrelated entries. No error, ever.

### I-08 · every input returns the same value
- **GIVEN** a mutation returns `false` for the legitimate role AND every privileged role
- **BAD** "role allowlist ENFORCED"
- **GOOD** control == probe ⇒ **UNREADABLE**. Characterise the oracle before verdicting.
- **WHY** an account-level gate answered before the role was consulted.

### I-09 · wrong host, error page read as enforcement
- **GIVEN** three probes return 403
- **BAD** "enforced"
- **GOOD** read the BODY — an HTML error page from the edge is not the app. Assert
  `location.hostname` at the top of every console batch on a multi-host target.
- **WHY** the GraphQL lived on the other host.

### I-10 · catch-all endpoint read as a real one
- **GIVEN** `/actuator/env` returns 200
- **BAD** "Spring actuator exposed"
- **GOOD** send a nonsense sibling (`/actuator/ZZ-CANARY-37`). Same 200 ⇒ catch-all responder.
- **WHY** every actuator path returned the 2-byte body `OK`, including invented ones.

### I-11 · positional-argument slip
- **GIVEN** a helper called as `post(label, TEXT, EMAIL)` when it expects `(label, EMAIL, TEXT)`
- **BAD** a clean-looking ENFORCED verdict
- **GOOD** **log the value actually sent**, not the value intended.
- **WHY** caught only because the bot echoed the email back in its reply.

### I-12 · benign control fails ⇒ BROKEN, not enforced
- **GIVEN** an endpoint times out with 504 under test
- **BAD** "enforced"
- **GOOD** request it with NO parameters. Still 504 ⇒ broken ⇒ **UNREADABLE**. (Also hunt #30.)
- **WHY** a dead endpoint and a hardened one are indistinguishable without the benign control.

### I-13 · no reachable success state
- **GIVEN** every input to a lookup returns the same "not found", including known-good ones
- **BAD** "input rejected ⇒ enforced"
- **GOOD** if NO input produces a success there is no oracle ⇒ UNREADABLE for that endpoint.
- **WHY** nine `pageUrl` forms, all identical.

### I-14 · generated query mis-declares nullability / list-ness
- **GIVEN** `VARIABLES_IN_ALLOWED_POSITION` or `SCALAR_LEAFS` on BOTH legs
- **BAD** counting the pair as a result
- **GOOD** a schema-shape error on both legs is MY defect — leaf-name extraction drops LIST/NON_NULL
  wrappers. Fix the generator or inline the literal, then re-run.
- **WHY** three separate occurrences in one hunt.

### I-15 · the control differed from the probe in MORE THAN ONE variable
- **GIVEN** a control that fails while the probes are untried
- **BAD** reading the failure as a signal about the target
- **GOOD** §4 says the control runs the SAME code path. Diff the two request bodies field by field
  before blaming the server; if they differ anywhere but the thing under test, the control is not a
  control.
- **WHY** 2026-09-06, chatbot outbound-tool probe. Control sent `page_dom:''`, probes sent a
  populated DOM — two differences, not one. The 500 was mine. One wasted batch, and for a moment it
  looked like the endpoint had broken since the hunt closed.

### I-16 · a banked request shape records field NAMES without TYPES
- **GIVEN** a request replayed from notes returns `500` / a deserialization error
- **BAD** concluding the endpoint changed or broke
- **GOOD** read the raw error — `Cannot deserialize value of type X from Y` names the exact field
  and the type it wanted. Then fix the NOTE, not just the batch. Bank shapes with types:
  `notifications: String` not `notifications`.
- **WHY** 2026-09-06. The resume note said `dom_json:{notifications, page_dom}`. `notifications` is
  a `java.lang.String`; I sent `[]`. Four of seven diagnostic shapes 500'd on it. Sibling of I-14 —
  same defect (a shape recorded without its type), different source (a hand-written note, not a
  generator).

### I-17 · an identifier scraped from the page is not an identity assertion
- **GIVEN** a probe needs to know "which tenant am I?" and the page contains an id-shaped string
- **BAD** regexing the loaded HTML for `company_id` / `account_id` / `tenant` and treating the first
  hit as your own identity
- **GOOD** take identity ONLY from something the server returns FOR YOUR SESSION: a response header,
  or an authenticated account/me endpoint. Validate the oracle against a control endpoint BEFORE
  building any comparison on it.
- **WHY** 2026-09-07. An endpoint that takes no identifier returned a record stamped with a company
  id that did not match the one scraped from the page, and it reproduced 3/3. It read as a clean
  cross-tenant disclosure and a report was one step from being drafted. The scraped id belonged to
  the VENDOR: the app embeds the vendor's own analytics tag, so the page carried the vendor's tenant
  id alongside ours. The true identity was in a response header present on every single request, and
  in the account's own API-keys response. Both were visible in the first screenshot.
- **The compounding failure, which is the real lesson.** Three separate "disambiguation" batches were
  run before filing. Every one of them was constructed on the assumption that the scraped id was
  ours, so none of them could detect that it was not. **A control built on an unvalidated premise
  validates the premise, not the claim.** Ask of every control: *what reading does this rule out?*
  If the answer does not include "my own starting assumption", it is not disambiguating anything.
- **Caught by:** HUMAN. Kiran sent a screenshot that happened to include the response headers. The
  console output that had been requested would not have contained them.

---

> **The family these share.** I-01 · I-07 · I-07b and the C04 benchmark slip below are one shape:
> **the system's representation of reality diverged from reality without raising an error.** Three
> instances landed on 2026-09-06 alone — an extractor that could not represent `:param` routes (the
> surface looked smaller), a scoring harness using substring matching (capability looked better), a
> retriever blind to a new schema (knowledge looked absent). None crashed; all three produced
> confident wrong readings, and two of them read as GOOD NEWS. Design rule that follows: every
> component whose output can be *empty, clean, or complete* must carry a way to fail loudly —
> a self-check, a positive control, or a known-present probe.
>
> **Recurrence, 2026-09-06 (I-03 family):** the batch printed `JSON.stringify(c.last).slice(0,200) || c.raw`. `JSON.stringify(null)` is the STRING `"null"` — truthy — so the fallback never fired and the 500 body was invisible for a whole round trip. A logging expression that can silently swallow the error is the same defect as a probe that cannot fail loudly. Print the raw body ALWAYS, never behind `||`.

## 2 · REASONING — the observation was fine, the inference was not

### R-01 · verdict from a filter that matched nothing
- **GIVEN** a DevTools filter shows no GraphQL traffic
- **BAD** "this target is REST, not GraphQL"
- **GOOD** an empty filter is not evidence of absence. Parse the capture.
- **WHY** the HAR held 90 `/graphql` POSTs.

### R-02 · one sub-lane reported as the lane
- **GIVEN** three authz probes on a chatbot all enforce
- **BAD** "CHATBOT LANE ENFORCED"
- **GOOD** name the denominator: conversation-scoping enforced, **3 of ~11 sub-lanes**; the LLM lane
  is NOT TESTED.
- **WHY** system-prompt extraction, injection, tool discovery and exfil were untouched.

### R-03 · steerable ≠ vulnerable — whose boundary breaks?
- **GIVEN** a client-supplied field visibly changes a tax computation
- **BAD** "business-logic finding"
- **GOOD** ask **whose boundary breaks**. All four calculator fields were in the UI ⇒ the user is
  misstating their own return ⇒ self-harm ⇒ **N/A**.
- **WHY** asking early avoided a rejected report.

### R-04 · two selectors cannot separate honoured from ignored
- **GIVEN** own object → ok, foreign object → ok
- **BAD** "FALSIFIED — cross-tenant"
- **GOOD** send a THIRD selector belonging to NOBODY. Same ok ⇒ the argument is ignored ⇒ N/A.
- **WHY** killed two candidates that both looked like findings.

### R-05 · impact claimed beyond what was shown
- **GIVEN** a cross-tenant write lands in another user's document store
- **BAD** "enters the victim's tax filing workflow"
- **GOOD** state what WAS achieved and what was NOT, then set the CVSS metric to match.
- **WHY** the narrower claim is the one that got triaged.

### R-06 · two captures compared as wall-clock
- **GIVEN** HAR A stamped `Z`, HAR B stamped `+04:00`
- **BAD** ordering events by the printed strings
- **GOOD** normalise to UTC. Two captures of one flow are ONE timeline.
- **WHY** a 2-minute sequence was inverted into 4 hours; a working control was declared contaminated.

### R-07 · classifying documents by their filename
- **GIVEN** 39 PoC folders
- **BAD** classifying 36 by name, reporting "31 of 39 not our lane"
- **GOOD** read all of them; state read-vs-total. The one filed as "browser/binary" was an **LLM
  assistant data-exfiltration chain** — the exact chain we had failed to complete that same day.
- **WHY** [[read-every-writeup-fully]], third instance.

---

## 3 · COVERAGE — the number was true and still misleading

### C-01 · depth on one class read as coverage of all
- **GIVEN** ~500 requests, 83/219 mutations verdicted, two reports filed
- **BAD** ready to close
- **GOOD** build the class matrix — **three of ten classes had ZERO probes.**
- **WHY** the rule existed twice and still did not fire, because no ARTEFACT made the gap visible.

### C-02 · a class marked covered by the wrong evidence
- **GIVEN** 52 MB of JS mined and secret-scanned
- **BAD** "class 8 covered"
- **GOOD** bundle mining ≠ runtime config. Fetch `/config.js`, `/env.js`,
  `/internal/config/anonymous` UNAUTHENTICATED. No byte count + no config probe ⇒ UNTESTED.
- **WHY** the step had never run.

### C-03 · a partial inventory that looks complete
- **GIVEN** "365 String input fields"
- **BAD** treating it as the input surface
- **GOOD** a typed API takes attacker input in FIVE places: arguments (1037), input fields of every
  type (1041), enums (154), custom scalars (15), the query root.
- **WHY** the first number was String-only and 64% low.

### C-04 · a fraction that hides its own structure
- **GIVEN** `83 / 219 mutations verdicted`
- **BAD** quoting it bare — reads as "62% untested"
- **GOOD** decompose: 212 gated / 7 outside; 83 exercised / 129 not; state the shared-interceptor
  evidence AND that it is not assumed to cover the 129.
- **WHY** both "83/219 safe" and "only 83 tested" are wrong.

### C-05 · the denominator that hides a zero
- **GIVEN** `8 / 251 textual fields probed`
- **BAD** "injection surface sampled"
- **GOOD** type it. 373 money/custom-scalar fields sat at **0** — on a TAX product, where a parser
  that disagrees with the UI is a business-logic bug.
- **WHY** the honest denominator exposes the untouched population.

### C-06 · untestable quietly becoming safe
- **GIVEN** a lane unreachable without a paid tier
- **BAD** omitting it, or folding it into "enforced"
- **GOOD** `UNTESTABLE — <prerequisite>` with a blocker type. Five TIER blockers in one hunt is
  target-selection intelligence.
- **WHY** "untestable" never becomes "safe".

---

## 4 · STOP / PIVOT — knowing when to leave a lane

### S-01 · a proven gate kept being re-proven
- **GIVEN** a shared authz interceptor enforced across 83 mutations, 0 exceptions
- **BAD** testing mutation #84
- **GOOD** marginal value ≈ 0. Pivot to what does NOT traverse the gate: sibling services, other
  selector families, workflow transitions. [[pb0726]]
- **WHY** the one filed cross-tenant write lived on the service that never touched it.

### S-02 · a control leg that mutates lifecycle
- **GIVEN** a sweep whose control writes to my own object
- **BAD** excluding only verbs that DELETE
- **GOOD** a control leg is a WRITE. Exclude any verb changing LIFECYCLE or STATE
  (`archive` · `start` · `initiate` · `revise` · `revert` · `generate` · `import` · `dismiss`).
- **WHY** v1 archived the operator's own marker entity; no unarchive mutation exists.

### S-03 · missing prerequisite ≠ deprioritised
- **GIVEN** the highest-value remaining lane needs two real phone numbers
- **BAD** "we should have prioritised it"
- **GOOD** `MISSING_STATE — prerequisite unavailable`. Do not pretend an executable test existed.
- **WHY** honest blockers are what make the untested list trustworthy.

### S-04 · a probe that would reach humans
- **GIVEN** an assistant offers to raise a support ticket
- **BAD** sending an injection payload to see what happens
- **GOOD** `NOT TESTED BY CHOICE — RoE`: the queue is read by real support staff; manipulating people
  is out of scope, as is service degradation.
- **WHY** the same reasoning retired the 50-alias amplification probe.

---

## close-out record — forensic, NOT scored

🚫 **No percentage. No `27/31`. No grade out of the file.** A number invites optimising against the
checklist, which is how a recognition aid quietly becomes a benchmark. Record each case that FIRED,
in prose, and nothing about the ones that did not.

**Per case that fired:**
```
Case:                <id + name>
Fired:               YES
Detected by:         JARVIS | deterministic control | human during hunt | post-hunt audit | ESCAPED
Impact:              what the wrong reading cost — a lane, a round, a false verdict
Recurrence:          first time | Nth time
Protocol change:     <the smallest fix> | none needed
New subsystem:       NO by default
```

⭐ **`Detected by` is the load-bearing field, and `ESCAPED` is the most valuable value in it.**
The same failure caught by a control twice is a different situation from one caught by JARVIS the
second time, and both differ from one nobody caught until the audit. That distinction is the only
honest evidence for whether a proposed subsystem is needed.

**The decision rule this feeds — and the ONLY route to new architecture:**
```
failure fires
    -> already in EVAL_SET?
         no  -> add the case. stop. build nothing.
         yes -> recurrence
                  -> can a PROTOCOL or CONTROL change prevent it?
                       yes -> change the protocol. build nothing.
                       no  -> only now consider a subsystem
```
Every new JARVIS subsystem must correspond to an OBSERVED failure the existing system cannot handle.
Not a predicted one. [[phase-shift-hunt-not-build]]

---

## hunt #37 baseline — the record to beat
Not a score; a list of what fired and who caught it.
```
I-01 sweep FALSIFIED 0 / UNREADABLE 109   detected by: JARVIS (noticed the pairing)   impact: none, caught pre-verdict
I-02 row count as oracle                  detected by: JARVIS (content pull)          impact: 1 round
I-03 truncated chatbot response           detected by: JARVIS                         impact: 4 probes re-run
I-04 DOM probe on the wrong entity        detected by: deterministic control          impact: 3 rounds
I-05 OAST tail not running                detected by: JARVIS (self-test added)       impact: 1 false negative avoided
I-06 payload eaten by basename            detected by: JARVIS (stored-value print)    impact: 1 round, cmd lane re-run
I-07 schema parser 374 vs 219             detected by: HUMAN (Kiran recalled 219)     impact: would have been quoted
I-08 blind oracle, false for everything   detected by: deterministic control          impact: none
I-09 wrong host, 403 HTML error page      detected by: JARVIS (read the body)         impact: 1 batch
I-11 positional-argument slip             detected by: deterministic control          impact: 1 run, false ENFORCED
I-12 /launchpad 504 with no params        detected by: JARVIS (benign control)        impact: none
I-14 nullability mis-declared x3          detected by: deterministic control          impact: 3 rounds
R-02 chatbot lane called ENFORCED         detected by: HUMAN                          impact: lane reopened, 3->9 sub-lanes
R-05 impact overclaimed pre-filing        detected by: JARVIS                         impact: none, narrowed before filing
R-07 39 PoCs classified by filename       detected by: HUMAN                          impact: missed pb0734, the LLM exfil chain
C-01 three classes at ZERO probes         detected by: HUMAN                          impact: hunt nearly closed incomplete
C-02 class 8 covered w/o runtime config   detected by: post-hunt audit (matrix build) impact: none, fixed same day
S-02 archiveEntity on the control leg     detected by: ESCAPED                        impact: operator's marker entity archived, unrecoverable
```
**17 fired. JARVIS 7 · control 4 · human 4 · audit 1 · ESCAPED 1.**
The escape (S-02) is the one that did real damage. The four human catches are the gap to close.

---

## hunt #38 running record
```
I-17 scraped id read as own identity      detected by: HUMAN (screenshot showed Cid header)
                                          impact: NONE - falsified before filing. Would have been
                                          a false cross-tenant report against a mature programme.
I-blob 193 base64 WASM slices as tokens   detected by: JARVIS (count was implausible)   impact: none
I-0x08 regex compiled with a control byte  detected by: JARVIS (suppressor output review) impact: two
                                          suppressors were silent no-ops for an unknown period
I-heredoc backslash eaten x3              detected by: JARVIS                          impact: ~20 min
```
**The pattern across I-17 and hunt #37's I-07 / R-02 / R-07 / C-01: the human catches are all
CROSS-CHECKS AGAINST AN INDEPENDENT SOURCE, not deeper analysis of my own output.** That is the gap.
Concretely, for hunt #39: before any cross-tenant claim, the identity oracle gets its own control leg.

### I-18 · the control was chosen on an axis the oracle cannot move
- **GIVEN** a differential probe whose verdict rests on "did the response change?"
- **BAD** proving sensitivity with any pair that merely *feels* different, then reading every
  no-change leg as the server rejecting the input
- **GOOD** pick the sensitivity pair on an axis where the server is KNOWN to respond - ideally one
  already observed responding in the capture - and compare CONTENT (hash), never size alone
- **WHY** 2026-09-07, a marketing-automation target, `POST /template/<tid>/preview`, testing whether it honours an inline
  content field. Two failures, same endpoint, same session, opposite wrong answers:
  1. Diffed response BYTE COUNT. Both campaign ids are 26-char ULIDs, so substituting one for the
     other changes which bytes but not how many. 11 field legs returned "identical" and were one
     step from being banked as ENFORCED / mass-assignment falsified.
  2. Switched to a hash, then chose the sensitivity pair as campaign A vs campaign B - both VALID.
     Preview does not interpolate campaign content, only whether the campaign resolves, so that is
     precisely the axis the oracle is blind to. It reported the lane UNTESTABLE for an endpoint that
     is perfectly testable.
  The correct pair (valid vs belongs-to-nobody) was already in the walk HAR: own 35395B, ghost
  32400B. With it, sensitivity showed -2995B / different hash, and the 11 legs then falsified
  cleanly on real evidence.
- **The lesson.** A control that cannot fail is not a control; it manufactures whatever verdict the
  harness defaults to. The same endpoint yielded ENFORCED in pass 1 and UNTESTABLE in pass 2 purely
  from how the control was specified. Before running any differential, state which observable the
  control would change and cite where that observable was previously seen changing.
- **Caught by:** SELF, but only because a sensitivity leg was demanded before banking. The first
  pass had no such leg and its false ENFORCED was already written into a response.

### I-19 · the control was built from a SCRAPED identifier, so it was never a control
- **GIVEN** an object-selector probe (IDOR shape) where the "own object" leg is an identifier
  harvested from page HTML, a bundle, or an archive — rather than one the application itself used
- **BAD** treating that scraped id as the must-succeed leg, then reading N identical refusals as the
  endpoint enforcing authorization
- **GOOD** obtain the selector from a CAPTURE — drive the feature and read the request the app
  actually sends. Only an id the application used is a valid control
- **WHY** 2026-09-14, an insurance group's unauthenticated `getJsonDocument({id})` endpoint — the
  only real lead on the target. Six legs: two "controls" (GUIDs scraped from the calculator pages),
  a null GUID, a random GUID, a malformed value, and empty. **All six returned an identical
  `404 / 0 bytes`.** The endpoint was correctly recorded UNREADABLE rather than ENFORCED — but the
  cause was not the target. Page GUIDs are component, template or analytics ids; none of them is a
  document id, so **no leg could ever have succeeded.**
  Then a second failure on top of the first: I explained the 404s as the missing Sitecore
  curly-brace id format. Re-testing the SAME id **unbraced** returned a byte-identical `200`,
  disproving it outright. The tidy explanation had been accepted for one message before the
  disproving leg ran.
  What resolved it: opening the calculator in a browser and reading the real request off the
  network tab — `?id={441080D3-…}` — in about sixty seconds. With that id as the control the probe
  became readable immediately, and the lane FALSIFIED honestly (public config, no PII).
- **The lesson.** Two rules, both violated in one probe. (1) **A scraped identifier is not a
  control** — a control must be an object the application demonstrably accepts, which usually means
  a capture, not a bundle. (2) **When every leg including the control is identical, suspect your own
  input before the target's behaviour**, and test the explanation you just invented by running the
  leg that would falsify it. `pb0766`.
- **Caught by:** SELF for the UNREADABLE verdict (the control rule held, and stopped a false
  ENFORCED). SELF for the braces error too, but only because the unbraced leg was run —
  had it not been, a wrong explanation would have been written into the matrix as fact.


---

### I-20 · the test setup destroyed the signal it was measuring
**Hunt #41, 2026-09-16.** To get "a clean signal" I ran `am force-stop the app package` before sending
the PoC broadcast. Force-stopped Android apps are in the **STOPPED** state and receive **no broadcasts
at all** (`FLAG_EXCLUDE_STOPPED_PACKAGES`). The null result was guaranteed by my own setup, not by the
target's behaviour.
**Shape:** a hygiene step added *for* cleanliness silently became the independent variable.
**Catch:** ask of every null result — *could my setup alone have produced this?* Re-run with the
setup step removed before recording anything.

### I-21 · path translation silently rewrote the instrument's target
**Hunt #41.** `adb shell uiautomator dump /sdcard/c.xml` under Git Bash reported
`dumped to: /Files/Git/sdcard/c.xml` — MSYS rewrote the **device** path. Every subsequent read came
back empty, and I nearly recorded "the premium activities display nothing", the **opposite** of the
truth (they display a paywall).
**Caught by:** the control screen (Settings) reporting **0 text nodes**, which is impossible.
**Fix:** `MSYS_NO_PATHCONV=1` for any command whose path argument belongs to another OS.

### I-22 · the oracle does not discriminate, so the batch proves nothing
**Hunt #41.** `am broadcast` prints `Broadcast completed: result=0` whether or not a receiver runs.
Target and control produced byte-identical output. Compounding it, the "control" component
(`OtpSmsReceiver`) **did not exist** — a name I assembled from an unrelated dex string, which is
`I-19` repeating inside the same hunt.
**Rule:** before trusting a batch, verify the control component EXISTS, and verify the oracle can
produce two different outcomes.

---

# HUNT #41 AUDIT — 2026-09-16. 40 signatures walked, not sampled.

## OCCURRED, SELF-CAUGHT (13)
| sig | what happened |
|---|---|
| I-07 | Common Crawl's JSON **error object** was counted as a record; control returned 1 where it must return 0. Fixed to count only lines carrying a `url` key |
| I-08 | `/api/who-called-me/<n>`: own number and 2 controls all identical. Recorded **PARTIAL**, not "enforced" |
| I-10 | a second-tier host on the target answers **200 / 14 327 b for every path incl. control**. Would have filed "source maps exposed"; the same-batch control killed it |
| I-11 | `curl -w` with an extra positional argument fired a **second request** — twice. Those `000` lines were mine |
| I-12 | CRLF in a command file → curl `000`, which mimics an IP block. Diagnosed with a control each time; fixed structurally with `newline='
'` |
| I-19 | built a control component (`OtpSmsReceiver`) out of a **string scraped from the dex**. It never existed ⇒ was never a control |
| I-20 | `am force-stop` before the broadcast test — stopped apps receive no broadcasts, so the null result was guaranteed by my own setup |
| I-21 | MSYS path translation rewrote `/sdcard/c.xml` → `/Files/Git/sdcard/...`. Caught only because the Settings control reported 0 text nodes |
| I-22 | `am broadcast` prints `Broadcast completed: result=0` whether or not a receiver ran ⇒ target and control identical ⇒ batch proved nothing |
| C-03 | notes asserted **"55 hosts" and "66 hosts"**; only 11 were recoverable. Rebuilt from CT: 86 names, 15 in-scope, union 32 |
| C-05 | Wayback `limit=40000` returned **exactly 40000**; Common Crawl `limit=4000` returned **exactly 4000**. A result equal to the limit is a cap |
| R-05 | pitched a third-party-platform endpoint as disclosing other merchants' `partnerKey`. Reading the call site showed **no client-supplied selector exists**. Retracted |
| I-23 | **NEW** — see below |

## OCCURRED, KIRAN CAUGHT (3)
| sig | what happened |
|---|---|
| C-01 | said **"looking like a fortress"** with 9 of 11 classes `NOT TESTED`. *"dont tell me this is a fortress before finishing everything"* |
| C-06 | recommended parking `/directory/` having probed **nothing** on it. *"we have not tested anything"* |
| C-07 | **NEW** — the micro-class audit. *"check properly"* |

## NOT OBSERVED THIS HUNT (24)
I-01 · I-02 · I-03 · I-04 · I-05 (no OAST used) · I-06 · I-07b · I-09 · I-13 · I-14 · I-15 · I-16 ·
I-17 · I-18 · R-01 · R-02 · R-03 · R-04 · R-06 · R-07 · C-02 · C-04 · S-01 · S-02 · S-03 · S-04

```
INSTRUMENT QUALITY = self-caught / total occurred = 13 / 16 = 81%
```
⚠️ Read it honestly: the three Kiran caught were all **coverage/stop-pivot**, never instrument. My
instruments catch my instruments; they do not catch **me deciding I am finished**. That is the same
split as every prior hunt and it has not moved.

---

### C-07 · a verdict was REACHED but never entered in the instrument
- **CLASS** coverage
- **WHY** 2026-09-16. The micro table held 14 rows. Six verdicts we had actually reached were sitting
  in prose only — subdomain takeover (N/A, reasoned), insecure deserialization, Universal-Link hijack
  (FALSIFIED against a control), App-Links delegation (FALSIFIED via code search), the gRPC oracle
  (UNTESTABLE/ROE) — and, worst, **the Android exported-receiver finding: the hunt's ONLY confirmed
  finding, the entire report #1, had no row at all.** Three further classes (cache poisoning, cache
  deception, request smuggling) had never been considered anywhere.
- **DISTINCT FROM C-03** — C-03 is an inventory that is genuinely incomplete. Here the WORK was done
  and the VERDICT was reached; only the accountability artefact never recorded it. A matrix that omits
  your own finding cannot show you what is missing.
- **CATCH** after every probe run, ask: *does this verdict have a ROW?* And at close, diff the rows
  against the findings list — a finding with no row is an automatic fail.
- **WHO CAUGHT IT** Kiran, on the third "check properly" of the hunt.

### S-05 · a lane was ranked best-in-hunt without checking its FIRST precondition
- **CLASS** stop/pivot
- **WHY** 2026-09-16. Called an embedded-platform API lane *"the best untested lane in this
  hunt"* across three turns, and wrote a full console-batch instrument for it. I had checked the
  bundle, the API, the auth model and the JWT claim structure — but never whether the app could still
  be **installed**. the platform's own listing says *"This app is not currently available"* on that store The lane was never reachable. Kiran was mid-signup for a partner account on that platform when
  the search returned 15 unrelated apps.
- **CATCH** before ranking any lane, test its cheapest gating precondition FIRST — can I obtain the
  credential / install the app / reach the tier at all? Order preconditions by cost, not by interest.
- **WHO CAUGHT IT** Kiran's screenshot, though I diagnosed the cause.

### I-23 · a success-shaped response that means the backend gave up
- **CLASS** instrument
- **WHY** 2026-09-16. GitHub `/search/code` answered a `repo:`-qualified query with **HTTP 200** and
  `{"total_count":0,"incomplete_results":true,"items":[]}` — no error, no message, reproducible 3/3.
  The same term with `org:` returned 1576 complete. Reading `total_count` alone cannot separate
  "nothing matched" from "the query timed out", and the whole target-identifier sweep would have
  been recorded as **"no leaked identifiers found"** from a green 200.
- **DISTINCT FROM I-03/C-05** — nothing was truncated and no limit was hit. The API *declares* its own
  failure in a field beside the number, and the failure is invisible to anyone reading the number.
- **CATCH** gate every verdict on the API's own completeness field, never on the count. Run the
  positive control FIRST: the control failing is what exposed this.
- **WHO CAUGHT IT** self, via the instrument positive control (`pb0767`).

### C-03 RECURRENCE LOG — hunt #41, four passes on one denominator
- **WHY** 2026-09-16. The in-scope host count went **66 → 32 → 148 → 157** across one hunt. Pass 1 was
  a number with no list behind it. Pass 2 came from Certificate Transparency and I called it *"the real
  breadth denominator"* — CT cannot see hosts behind a wildcard certificate. Pass 3 came from the APK
  dex and I reported it as final — I had mined **only the dex**, not `assets/`, not `resources.arsc`.
  Pass 4 came from the target's OWN service registry plus one hostname in `assets/`.
- **THE SHAPE** every correction arrived from a **source I had not yet mined**. Not one came from
  re-examining the number I had just defended. Each new source made the previous total look complete
  in hindsight and authoritative at the time.
- **CATCH** before stating any denominator, list the corpora NOT yet mined and say so next to the
  number: *"157, from dex + assets + registry; NOT from urlscan (capped 100/649) or Wayback."* A
  denominator without its source list is pass-1 again under a bigger number.
- **WHO CAUGHT IT** Kiran, four times, each time by asking me to check again rather than by supplying
  the answer.

### C-08 · the matrix was never CREATED — five days of verdicts with no instrument
- **CLASS** coverage
- **WHY** 2026-09-22, hunt #42. `HUNT_PROTOCOL.md` §3.5 says the matrix is its own file,
  `workspace/coverage/<target>_matrix.md`, **created at the FIRST capture with every row
  `NOT TESTED`** — "a matrix built at close is a report; a matrix built early is an instrument."
  It was never created. Across five days the hunt produced two HARs, five probe runs, ~70 requests
  and **six ENFORCED verdicts — all six inside class 1** — while ten of eleven classes sat at zero
  probes and class 10's sink inventory was never built at all. The working-notes file grew to 1135
  lines, which felt like thorough documentation and functioned as the opposite: no artefact
  anywhere showed that ten classes were empty.
- **DISTINCT FROM C-07** — C-07 is a verdict missing its ROW in a matrix that exists. This is the
  matrix not existing. C-07 is auditable and self-correctable at close; this is not auditable at
  all, by anyone, including me. It is also distinct from C-03: no denominator was wrong here, they
  were all stated correctly — in the wrong artefact, one that cannot show absence.
- **THE SHAPE** depth inside one class reads as progress. Six verdicts with passing controls felt
  like a well-run hunt, and by every local measure it was. Completeness is not visible from inside
  the class you are working in, which is the entire reason the protocol puts the instrument
  outside the notes.
- **CATCH** the matrix file is created by the same action that opens the target file — not later,
  not "once there is something to put in it." An empty matrix full of `NOT TESTED` **is** the
  point. Before any second probe run in a hunt, confirm the file exists on disk.
- **WHO CAUGHT IT** Kiran — *"build the matrix file first how can u forget to build it bro..very
  bad"* — after five days. Not self-caught, and `/hunt` reporting "0/11 classes" in my own state
  report one turn earlier did not trigger it either.

### I-24 · UNREADABLE became a resting place instead of a repair order
- **CLASS** instrument
- **WHY** 2026-09-22, hunt #42. On 2026-09-17 a probe's positive control returned 401 on an
  endpoint that had returned 200 in the capture minutes earlier. I correctly recorded the run as
  **UNREADABLE** — and then moved to a different asset and left it. Five days later the same lane
  was re-run with one added request header and the control passed immediately, 16.5 KB of data.
  The class sat at UNREADABLE in the coverage matrix the entire time, indistinguishable at a
  glance from a lane the target had actually closed.
- **DISTINCT FROM `pb0767`** — that rule says an instrument failing its control cannot issue a
  trusted negative, and it worked: no false verdict was banked. The failure here is what happened
  AFTER the correct verdict. UNREADABLE is the one verdict in the vocabulary that describes *my*
  equipment rather than the target, so it is the only one that carries an implicit to-do. Treated
  as terminal, it silently converts an instrument bug into apparent coverage.
- **THE SHAPE** the other five verdicts are conclusions; UNREADABLE is a fault report. Filing a
  fault report and closing the ticket is not the same as fixing the fault.
- **CATCH** an UNREADABLE row names the SUSPECTED CAUSE and the REPAIR, not just the failure, and
  is re-attempted before the hunt advances to another asset. If the cause is unknown, that is the
  next experiment — not a reason to move on.
- **WHO CAUGHT IT** self, but only after Kiran said "rerun the e series" — the decision to go back
  was his, not mine.

### I-25 · endpoint-level control mistaken for field-level control
- **CLASS** instrument
- **WHY** 2026-09-23, hunt #42. A config-update endpoint took a ~20-field object. I tested six
  fields for REFUSAL of a bad value — an unknown enum member, a real-but-not-offered one, an
  invented one, a widened allowlist — and read all six "did not persist" as "the server
  validates". The probe had **no control at all**. The follow-up control picked a display-name
  field I had never shown to be writable; it did not move, and I nearly concluded the write path
  was dead. A third run used a field proven writable in an earlier stage, and it moved — which
  established only that the ENDPOINT works.
- **THE SHAPE** a control on endpoint E proves E accepts writes. It says nothing about whether
  FIELD f inside E is writable. If f is simply read-only on that handler, then "rejects the
  dangerous value" and "rejects the nonsense value" are the same non-event, and neither is a
  security property. A silently-ignored field and a validated field produce identical evidence:
  200, unchanged state.
- **DISTINCT FROM `pb0767` / I-24** — those cover an instrument whose control FAILS. Here the
  control PASSED and was still the wrong control, because it was scoped to the wrong object.
- **CATCH** every field under test needs its own **benign positive control**: same field, a value
  that SHOULD be accepted, proven to persist by read-back. Only then does a refusal mean anything.
  If no benign value exists that is safe to send — e.g. a visibility flag whose only other known
  value would expose the object to third parties — the field is **UNTESTABLE**, never ENFORCED.
- **THE UNDERLYING HABIT** five separate misses in one hunt trace to one pattern: testing the
  negative case before establishing the positive one. Guessed a body shape before reading the call
  site; guessed field names before dumping the structure; tested refusals before testing
  acceptance. Read the benign case first, every time.
- **WHO CAUGHT IT** Kiran — *"also why is you controls failing all the time..check properly bro"*.
  I had reported each control failure honestly but treated them as unrelated accidents rather than
  one habit.

### I-26 · read-back inside the write-settle window manufactures refusals
- **CLASS** instrument
- **WHY** 2026-09-23, hunt #42. A config-update endpoint is **eventually consistent**: a measured
  **~3.2s** between the 200 and the value appearing on the matching read. My probes read back
  after **900ms** and recorded "did not persist" six times. I read that as "the server validates
  its inputs" and was one turn from writing six ENFORCED verdicts into the matrix. Re-run with a
  15s settle window, the controls landed at ~1.9s and ~2.9s and the real refusals held — same
  tests, opposite meaning.
- **HOW IT SURFACED** the probe's own summary contradicted itself: every test reported
  "did not persist", yet final state showed one more array member than the baseline. The writes
  had landed after the check AND after the restore. Without printing final state beside per-test
  results, nothing would have shown.
- **WHY IT IS ITS OWN SIGNATURE** `pb0767` and I-24 cover a control that FAILS; I-25 covers a
  control scoped to the wrong object. Here the control PASSED, was correctly scoped, and was still
  wrong — because it was sampled too early. A silently-ignored field and a not-yet-committed write
  are identical at t+900ms.
- **THE INVERSION** the danger is not a missed bug. It is that a timing artefact reads as a
  SECURITY CONTROL. Fast read-back systematically produces "the server rejected it" for a server
  that accepted everything.
- **CATCH** never verdict a write from a single read-back. **Measure the settle time once per
  endpoint** by toggling a field known to be writable and polling until it lands; then poll to at
  least 4x that, and treat "never landed" as the only negative. Print final state beside per-test
  results so a contradiction is visible rather than inferred.
- **WHO CAUGHT IT** Kiran — same question as I-25. Neither was self-caught.

### C-09 · the gate screened for ACCESS but not for OBSERVABLE EFFECTS
- **CLASS** coverage
- **WHY** 2026-09-23, hunt #42. The gate confirmed we could register, authenticate and reach the
  application on a free tier — and we could. What it never asked was whether that tier can produce
  an **observable effect**. Four independent lanes then died the same way, each after substantial
  work: a callback URL stored but never dialled ("not active on this plan"); an API token minted
  but refused at request time with a plan error; a server-side template writable but with no
  reachable renderer; a preview endpoint reached and authenticated but erroring because the account
  had no data to render.
- **THE SHAPE** on a free tier, **writes are reachable and effects are not**. Every one of those
  lanes produced a clean 200 on the write and nothing observable afterwards. A verdict needs the
  effect, so each closed as UNTESTABLE — which is honest, but it is coverage bought at full price
  and delivered empty.
- **WHY IT LOOKS LIKE SECURITY** an ungated write followed by silence is indistinguishable, at a
  glance, from a control that quietly refused. The write/effect asymmetry manufactures the
  APPEARANCE of enforcement in exactly the lanes where nothing was tested at all.
- **DISTINCT FROM #40's lesson** ("screen ACCESS first") — access was fine here. The missing
  question is one step further on: *given this account, which classes can I actually OBSERVE?*
- **CATCH** at gate time, pick the cheapest effect the target offers (a callback, a render, a
  generated document, a state change visible on a second endpoint) and confirm ONE fires end to
  end before committing lanes to it. If no effect is observable on the tier we hold, say so in the
  gate and expect UNTESTABLE verdicts — do not discover it four lanes deep.
- **WHO CAUGHT IT** self, but only after the fourth lane closed the same way; the pattern was
  visible after the second.

### R-05 · a lane retired on a principle instead of a measurement
- **CLASS** reasoning
- **WHY** 2026-09-23, hunt #42, second instance in one hunt. (a) I called a credential-minting
  endpoint a non-finding because I ASSUMED the tenant gate covering one path covered it too; the
  user asked "but we were able to create one — isn't that a finding?", I tested it, and it returned
  a clean ENFORCED verdict that had simply never been measured. (b) I marked a visibility flag
  UNTESTABLE because "no safe benign value exists to prove the field writable" — true-sounding, and
  wrong: a benign control is only needed for the NEGATIVE case, because a **persisting bogus value
  is self-controlling**. The user asked "what if it had a finding?", we built an exposure meter from
  a second tenant, and ran it safely. It came back negative — still a real answer, and one I had
  been about to bank as untested.
- **THE SHAPE** the dangerous retirement is not the lazy one, it is the WELL-ARGUED one. "The gate
  probably covers this" and "no safe control exists" both sound like discipline, and both close a
  lane with zero measurement behind them. A verdict backed by reasoning reads identical, in the
  matrix, to a verdict backed by evidence.
- **DISTINCT FROM I-25** — that is an instrument scoped to the wrong object. This is deciding not
  to build the instrument at all, for a reason that sounds like rigour.
- **CATCH** before retiring any lane on reasoning rather than a result, state the experiment that
  WOULD settle it and say explicitly why it cannot be run. If that sentence cannot be written
  concretely, the lane is not retired — it is unmeasured. In particular: "no safe control exists"
  must be checked against whether the POSITIVE outcome would be self-controlling.
- **WHO CAUGHT IT** the user, both times, with a one-line question. Neither was self-caught, and
  the second came after I had already written the first into the notes as a lesson.
