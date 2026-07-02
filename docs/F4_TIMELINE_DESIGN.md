# F4 — Execution Timeline (design seed)

*Not code. The schema, banked before implementation (the hard-to-change part). Next session
starts here. Phase 1 is frozen; F4 is a separate thread — no personality/prompt work.*

## Principle
Every pipeline stage is **independently inspectable**. Record not just *that* a step ran, but
*what it produced*. Keep three concerns separate internally:
- **Timeline** — what happened (immutable record).
- **Replay** — rerun a step/run from its recorded inputs.
- **Audit** — why (the reasoning/gate decisions; links to evidence).

The timeline is **immutable + versioned** (same discipline as the Evidence Object): written once,
everything downstream (viewer, replay, package) reads from it.

## Schema

```text
ExecutionTimeline
├── schema_version : 1
├── run_id         : uuid
├── target
├── started_at
├── finished_at
├── status         : running | ok | partial | failed
└── events[]
```

Each event:
```text
event_id
step            : subfinder | httpx | katana | nuclei | validate | evidence | export | ...
tool            : the binary/module + version if available
started_at
finished_at
duration_ms
inputs          : {args, target, prior artifact refs}
outputs         : {counts, summary}   # "143 domains", "17 findings"
artifacts[]     : [{name, path, kind}]  # subdomains.txt, alive_hosts.json, findings.json, evidence/
exit_code
status          : ok | skipped | failed
error           : str | null
parent_event    : event_id | null   # for nesting (per-finding under validate, etc.)
```

## Artifacts (the debugging superpower)
Record what each stage emitted so replay isn't only "rerun" — it's "show me exactly what
subfinder produced." Persist per-run:
```text
runs/<run_id>/
├── timeline.json
├── subdomains.txt        (subfinder)
├── alive_hosts.json      (httpx)
├── endpoints.json        (katana)
├── findings.json         (nuclei/probe)
└── evidence/             (F3 objects)
```

## Viewer target (platform feel, not logging)
```
Run 2026-07-02  (run_id ab12…)
  ✓ Subfinder     143 domains     2.1s
  ✓ HTTPX         121 alive       3.8s
  ✓ Katana        4,322 URLs      41s
  ✓ Nuclei        17 findings     18s
  ✓ Validate      4 confirmed
  ✓ Evidence      4 bundles
```
Feeds the HUD findings panel (I) + Phase-2 submission package (report.md + evidence.json +
timeline.json + traffic/ → zip).

## Build order (next session)
1. `core/timeline.py` — Timeline object + `start_run / record_event / finish_run`, versioned, persisted `runs/<run_id>/timeline.json`. Pure recorder, no pipeline coupling.
2. Instrument `ultron.bug_bounty` / `full_recon` stages to emit events + save artifacts.
3. Read side: `timeline show <run_id>` (the viewer) + `/timeline` HUD endpoint.
4. Replay: `replay <run_id> [step]` — rerun from recorded inputs. (Separate module from Timeline.)
5. Later (Phase 2): submission **package** — zip the run dir into a bounty deliverable.

## Guardrails
- Timeline immutable + `schema_version` (bump when the event shape grows).
- Recorder must never break the pipeline — wrap in try/except, degrade silently.
- Artifacts written under `data/runs/` (gitignored), not the repo.
- friday-recon parity from day one (shared `core/timeline.py`, port like F1/F3).
