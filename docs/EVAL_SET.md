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

