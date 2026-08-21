# Invariant Lens

A request-level lens for **behaviour discovery** — deciding what to *suspect* about a single
captured request, as opposed to enumerating what *exists* on a target.

> **Enumeration ≠ hypothesis generation.**
> Route tables, JS bundle mining and HAR coverage answer *"what exists?"*.
> This answers *"what assumptions does this request rely on?"*.

## Why this exists

Two filed bugs were traced back to one behavioural family:

> **The server enforces the UI's implicit contract instead of its own invariant.**

- A checkout UI exposed only a quantity control, so the server treated the whole item array as
  buyer-editable. The invariant should have been *"line items fixed by the merchant are immutable
  to the buyer"*.
- A redemption UI performed one checkout at a time, so the server read the usage counter and wrote
  it back without a lock. The invariant should have been *"check-and-consume is atomic"*.

Neither hypothesis came from endpoint enumeration. Both came from reading **one** request body and
asking what it took beyond the field the interface exposed. Depth on a single request beat breadth
across the route table.

## Scope and ethics

Only run this against traffic you are authorised to test, on a target in scope for an engagement or
bug bounty programme you are enrolled in. The lens produces *hypotheses*; each still has to be
tested with an own-object control and verdicted on server state, never on a status code.

---

## The lens

Input: **one captured request** — method, path, headers, body — plus a note of which fields the
user interface actually lets a normal user change.

For every field in the body (and every path/query parameter), answer four questions.

### 1. Ownership — who is supposed to decide this value?

| Class | Meaning | Suspicion |
|---|---|---|
| `client` | The actor legitimately chooses it | low |
| `server-derived` | Computed or looked up server-side | high if writable |
| `counterparty-fixed` | Set by the *other* party (merchant, admin, inviter, owner) | **highest if writable** |
| `system` | Identity, tenant, role, price, status, timestamps | **highest if writable** |

The bug lives where a field is `counterparty-fixed` or `system` **and** the request accepts it.

### 2. Interface exposure — can a normal user change this through the UI?

| Exposure | Suspicion |
|---|---|
| Exposed control (input, spinner, dropdown) | low |
| Present in the body but **no UI control exists** | **high** |
| Not in the body at all — try adding it | high |

A field the interface never lets anyone touch has usually never been threat-modelled as attacker
input. Note that "the API rejects unknown properties" is a *good* sign; "the API silently accepts
and applies it" is the finding.

### 3. Worst legal value — not malformed input, *valid* input the app didn't intend

Malformed values get caught by schema validation and prove nothing. Reach for values that are
type-correct and semantically legal:

- `0`, negative, fractional
- the declared maximum, and maximum + 1
- an empty collection, and the same element twice
- **another object of the same type that the actor legitimately owns elsewhere** — the cheapest item
  in the catalogue, a different plan, an expired coupon
- another tenant's identifier (always paired with an own-object control)

### 4. State assumptions — what does this endpoint assume about *when* it is called?

Ask, and mark each as an invariant candidate:

- **Sequential?** Does correctness depend on requests not overlapping? → concurrency test
- **Atomic?** Is there a read-then-write of a counter, balance, quota or seat count?
- **Single-use?** Tokens, invites, coupons, refunds, password resets
- **Ordered?** Must step N follow step N−1? Can a later step be called first?
- **Idempotent?** What happens on replay of the identical request?

---

## Output contract

The lens must emit, for each candidate, a **testable invariant** — not a vulnerability label.

```
BAD   "possible mass assignment"
GOOD  "`price_id` is merchant-fixed but accepted from the client; candidate invariant:
       line items on a merchant-created order must be immutable to the buyer"

BAD   "possible race condition"
GOOD  "usage counter is read at request start and written at completion (~4s apart);
       candidate invariant: check-and-consume of a single-use code must be atomic"
```

A label names a class. An invariant names something that can be **falsified by one test** — which is
the entire point.

Each candidate carries: `field` · `ownership` · `ui_exposed` · `invariant` · `test` · `priority`.

---

## Protocol (this part is the discipline, not the checklist)

1. **Write before discussing.** Run the lens and persist the output to a timestamped file *before*
   anyone talks about the request. A hypothesis produced after discussion cannot be attributed to
   the lens.
2. **Test with a control.** Every candidate is tested alongside an own-object control that must
   succeed. A failed control invalidates the test — it does not prove the target is safe.
3. **Verdict on state.** Re-read the object through the API afterwards. A `200` is not a result; a
   changed record is.
4. **Distinguish validation from enforcement.** A different error message means *untested*, not
   *enforced*. Compare the error against a known-bogus baseline before concluding anything.
5. **Cold replication.** A lens that only works with full engagement context in memory is intuition,
   not a procedure. Re-run it on the same request in a fresh session and check the same field
   surfaces.

---

## Worked example

> **This is a sanity check, not a result.** The example below is reconstructed from a bug that was
> already known when the lens was written, so it demonstrates the *format* of the output and nothing
> about the lens's ability to find anything on its own. Treat it as a worked exercise with the answer
> in the back of the book.

Captured request — a checkout that the interface renders with a single quantity spinner:

```
PATCH /checkout/{id}/items
{"data":{"items":[{"price_id":"pri_ABC","quantity":3}]}}
```

| Field | Ownership | UI exposed | Candidate invariant | Priority |
|---|---|---|---|---|
| `quantity` | client | yes | must respect the declared min/max | low |
| `price_id` | **counterparty-fixed** | **no** | items on a merchant-created order must be immutable to the buyer | **high** |
| `items[]` | counterparty-fixed | no (length fixed by UI) | the buyer cannot add or remove lines | medium |
| *(absent)* `unit_price` | system | n/a | price must be server-derived; a client-supplied unit price must be rejected | medium |
| whole request | — | — | concurrent PATCH + pay must not observe a stale total | medium |

The high-priority row is the previously observed bug pattern, and it sits on the one field the
interface never exposed. Again: the answer was known in advance here — this example is not evidence
that the lens independently discovered anything.

### Grading a real run

When the lens is run cold on a request nobody has discussed yet, the outcome falls into exactly one
of three buckets:

| | Outcome | Meaning |
|---|---|---|
| **A** | Novel hypothesis → survives verification | The capability is demonstrated |
| **B** | Novel hypothesis → false positive | Useful: tells you how much noise the lens generates |
| **C** | Nothing beyond what was already known | Independent hypothesis generation not shown yet |

Only **A** counts as a pass. **B** is still worth recording — a lens that produces confident nonsense
is worse than no lens, and only real runs reveal that rate.

## Relationship to the rest of the toolkit

- **Surface discovery** (route tables, bundle mining, capture coverage) decides *which* requests are
  worth putting under the lens. It does not replace it.
- **The auth matrix** covers object- and function-level authorisation. The lens covers the class of
  flaw where authorisation is intact but a field or a state assumption is not.
- Prefer the lens on anything that touches money, quotas, limits, roles, invitations or ownership.
