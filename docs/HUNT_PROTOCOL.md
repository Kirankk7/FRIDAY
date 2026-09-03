# HUNT PROTOCOL — share this at the START of every hunt

Kiran, 2026-09-04: *"you often dont go through the full methodology, sometimes bank it saying test is
done… make an md file which I'll share before every hunt so you don't make the mistake ever again."*

This file exists because of a specific, repeated failure of mine — **not** because the steps are hard
to remember. Read §0 first; it is the part I actually get wrong.

---

## §0 — MY FAILURE MODE, NAMED

I do not fabricate results. I **stop enumerating and let a partial pass stand as a complete one.**
Every time, the partial number *looked* whole, so nothing prompted a re-check.

| hunt | I said | reality | who caught it |
|---|---|---|---|
| a file-storage SaaS | "all classes enforced" | hadn't mined the JS bundles | Kiran |
| an EU retailer | "fortress, done" | 20 of 31 in-scope assets were mobile apps, never opened | Kiran |
| a tax SaaS | "185 mutations" | the runtime chunk map held 105 chunks my walk never loaded | Kiran |
| a tax SaaS | "365 input fields" | **1041** — I had counted only `String` | Kiran |
| a tax SaaS | "the input inventory" | **1037 arguments** never counted at all | Kiran |

**The rule that fixes it:** never state a coverage number without the total beside it.
`tested 365` is a claim. `tested 365 / 1041 known` is a fact. If I cannot produce the denominator,
I have not finished the enumeration and must say so instead of banking.

**Second failure mode:** verdicting off a probe whose positive control I never checked. Four times in
hunt #37 alone. See §4 — a result without a passing control is not a result.

---

## §1 — GATE (before any request)

- [ ] Programme is live, in scope, and I have the **exact** asset list. Count it **by type** — web,
      API, mobile, non-prod. Write the count down. (`pb0715`)
- [ ] Read the rules verbatim: required headers/markers, prohibited techniques, out-of-scope classes,
      severity table and the **pay cliff**. Note anything that makes a whole lane worthless.
- [ ] Ineligibility clauses (employee / customer / vendor). Never buy a paid plan to reach a lane.
- [ ] Safe harbour exists and covers what I plan to do.
- [ ] Record the venue's dupe policy and reward floor. If P3 pays nothing, the hunt is P2-or-nothing
      and cheap findings are not worth the hours.

**Hard rails, every hunt:** own accounts only · nothing destructive · never touch a third party's
data or identifiers · no scanning volume · HARs to the scratchpad, never the Desktop · never paste
live secrets into chat · nothing is submitted to a statutory/government system.

---

## §2 — LENS RUN (before any lane talk)

- [ ] First authorised capture → `python -m core.lens_run new <request> <label>`
- [ ] **Scrub before it leaves the machine**: cookies, auth headers, AND business identifiers —
      host, object ids, employer/company names, tax ids, addresses, trace/release ids. (`pb0720`)
- [ ] Cold sessions get the prompt **alone**. I contribute nothing until sealed.
- [ ] Replies → `HYPOTHESES.md` verbatim → `lens_run seal` → `verify` says INTACT.
- [ ] Only then may I discuss lanes.

A refusal from a cold model is a **result** — usually an audit of my prompt, not of the engagement.

---

## §3 — FULL SURFACE (the step I skip)

Enumerate the **machine-readable** surface **before lane selection** — not before the first
authorised capture. The order is deliberate:

```
authorised capture  →  cold lens (sealed)  →  surface enumeration  →  lane selection
```

The capture is evidence; enumeration tells you what else exists. Do not let "full surface first"
become a reason to delay the first real behavioural observation. Offline where possible.

- [ ] **Route/operation table.** SPA bundles: fetch the **runtime chunk map**, not just what the HAR
      loaded — the HAR is a sample, the manifest is the ceiling. Server-rendered: docs, `llms.txt`,
      `robots.txt`, sitemaps.
- [ ] **Schema, if GraphQL.** `python -m core.schema_surface <bundle> --gate <tenantArg> --out <dir>`
      — covers all FIVE input surfaces: arguments · input fields of **every** type · enums ·
      custom scalars · query root. Confirm `self-check: clean` before quoting any number.
- [ ] **Passive corpora**: Wayback CDX (URLs *and* archived bundles), urlscan, Common Crawl, source
      maps, GitHub code search on target identifiers.
- [ ] **Secret scan** the whole corpus.
- [ ] **Rank by the gate**: which operations sit OUTSIDE the tenant/authz boundary? Those are the
      surface once the gate is proven.
- [ ] **Write the counts into the target file.** Covered vs known, per category.

⚠️ Bundles served pre-gzipped need `curl --compressed`, else every regex silently returns zero.
⚠️ Minified GraphQL documents are doubly-escaped (`\\n`); one unescape pass returns almost nothing.
⚠️ Any extractor whose output is a COUNT needs an invariant that makes a wrong count LOUD. (`pb0712`)

---

## §4 — TESTING DISCIPLINE

**Every probe needs a positive control in the same batch.**

- [ ] Control uses an object I own, through the same code path, and MUST succeed.
- [ ] Control fails → the run is **UNREADABLE**. No verdict either way. Fix and re-run.
- [ ] Control returns an empty body → **blind oracle**. Pick a different endpoint.
- [ ] Two objects, two distinguishing strings — a response must name its own owner.
- [ ] Negative control recorded **before** the test, not reconstructed after.
- [ ] Different failure modes on the two sides are stronger evidence than two identical refusals —
      they show *where* the gate sits. (`pb0618`)

**Order:** falsify inside ONE account before building a second. Cheap self-only diagnostics first —
they predict where the authz lanes will land.

**Injection:** canary pass first — one unique marker per field, sorted into
STORED-INTACT / TRANSFORMED / REJECTED — then payloads only on the survivors. Never
`payloads × fields`; that is scanning and mostly teaches nothing.

**Two captures of one flow are ONE timeline.** Normalise every timestamp to UTC before ordering
across captures. Design the run so the interesting window is actually observed. (`pb0724`)

### Flow coverage — the second denominator

- [ ] For any multi-step workflow, record **observed transitions N / M known**, and preserve UTC
      ordering across every capture in the flow.

**A covered request is not a covered flow.** A request exposes *fields*; a flow exposes *state,
ordering, binding, replay and transition assumptions*.

Earned the hard way in hunt #37. The join→approve flow was captured on both sides and every field
analysed — but the requester made no state read in the **82 seconds** between its own join and the
admin's approval:

```
19:55:41  B  POST workspace/join   -> 200
          ·  ·  ·  82s UNOBSERVED  ·  ·  ·      <- the only window that could answer the question
19:57:03  A  PUT  .../accept
19:57:31  B  workspaces            -> ws=1
```

The capture proved access existed *after* approval and could never show whether it existed *before*.
Two full HARs, complete request coverage, and the actual invariant untested. Name the transitions
first, then design the run to observe the one that matters.

---

## §5 — VERDICT VOCABULARY (use exactly these)

| verdict | means |
|---|---|
| **ENFORCED** | tested, control passed, refusal observed |
| **FALSIFIED** | hypothesis tested and shown false |
| **UNTESTABLE** | no attacker path exists to try it (tier/admin-gated). **Never "safe."** |
| **UNREADABLE** | the control failed; the probe proves nothing |
| **N/A** | out of scope, or the class cannot exist on this stack — with the reason |
| **NOT TESTED** | honest admission; blocks closing the hunt |

Coverage is not complete until **every class and micro-class** carries one of these **with a reason**.

---

## §6 — BEFORE FILING

- [ ] Not on the never-submit list; not an out-of-scope class for this programme.
- [ ] The boundary crossed belongs to **someone else** — if only I am harmed, it is not a finding.
- [ ] Impact demonstrated on state, not on status codes. Raw error strings, not paraphrase.
- [ ] Never self-assign severity. State what I did **and did not** achieve. Frame it as **their
      missing control**.
- [ ] Title: `<class> on <host> through <endpoint> via <part> leads to <impact>`; CWE by
      **mechanism**, not effect.

---

## §7 — CLOSING

- [ ] Coverage matrix complete — every class verdicted with a reason.
- [ ] Denominators stated: `tested N / M known`, per category.
- [ ] Untestables listed explicitly, never folded into "enforced".
- [ ] Playbook entries added for what actually changes future action; target names scrubbed
      (public repo), pre-push hook hits enumerated individually.
- [ ] Memory + `docs/` updated; `bash /d/hunt-doctrine/sync.sh` + commit + push, unprompted.
- [ ] HARs and hunt artefacts deleted from the scratchpad.
- [ ] **Post-hunt retro, unprompted and honest**: what moved the needle, what I got wrong, what
      Kiran caught, and a grade on PROCESS not luck.

---

## §8 — THE ONE-LINE TEST

Before I say *done*, *closed*, *fortress*, or *enforced*:

> **Can I state the denominator?**

A denominator is required for both **breadth** (N/M surfaces) and **depth** (N/M transitions);
neither can be inferred from the number of requests sent.

If I cannot state it, I am banking a partial pass as a whole one — the exact failure this file
exists to stop. Say what is untested instead. An honest gap is worth more than a false close.

---

**FROZEN 2026-09-04.** Every rule here traces to a failure that actually happened. Do not grow this
file with checks that don't. The next hunt is the test of the protocol, not another revision of it.
