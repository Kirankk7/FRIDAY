# EVAL_SET — failure signatures, drawn only from failures that ACTUALLY happened

**v1, 2026-09-05. 31 cases, all from hunt #37 (ClearTax) unless noted.**

## what this is, and what it is NOT
A **recognition checklist and a post-hunt audit**. Not a benchmark.

🚫 **I do not score myself on it before a hunt.** I wrote it, I have seen the answer key, and a
self-graded eval on memorised cases is theatre — the same defect [[lens-run-every-hunt]] names when
it says *the assistant cannot be the cold context*. A number produced that way measures recall, not
judgement.

✅ **Two legitimate uses:**
1. **During a hunt** — when an output matches a GIVEN shape, apply the GOOD reading before verdicting.
2. **At hunt close** — walk every case and answer: *did this signature occur, and did I catch it or
   did Kiran?* That ratio is the [[post-hunt-retro]] `INSTRUMENT QUALITY` grade.

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

---

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

## audit template — run at hunt close

```
signature   occurred?   caught by ME or by Kiran?
I-01 .. I-14
R-01 .. R-07
C-01 .. C-06
S-01 .. S-04

new failure this hunt that no case covers?  -> ADD IT, and only then
INSTRUMENT QUALITY grade = self-caught / total occurred
```

**Hunt #37 baseline: 14+ signatures occurred; the two largest (C-01 zero-probe classes, R-07
filename classification) were caught by Kiran, not by me.** That is the number to beat.
