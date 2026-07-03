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
1. ✅ DONE `core/timeline.py` — Timeline object + `start_run / record_event / step / finish`, versioned, persisted `data/runs/<run_id>/timeline.json`. Pure recorder, no pipeline coupling. `load / list_runs` read side. (+parity, tested.)
2. ✅ DONE Instrument `ultron.bug_bounty` stages to emit events (recon/probe/idor/cve/validate/gate/evidence) + surface `run_id` in the result. Degrades silently. (+parity, wiring test.)
3. ✅ DONE Read side: `render / render_list` viewer + `/timeline` + `/timeline/<run_id>` HUD endpoints (JARVIS) + `timeline` CLI subcommand (recon). (+parity, tested.)
4. ✅ DONE Replay: `core/replay.py` `replay(run_id[, step])` — full hunt from recorded target, or per-step (`recon`/`probe`) from persisted artifacts (probe reruns against `endpoints.json`, no re-crawl). Refuses unknown steps / missing runs. Active-scan launcher → CLI-gated (`recon` `replay <run_id> --step`), no endpoint. (Unblocked by artifact+inputs persistence: `Timeline.write_artifact` + recon writes endpoints/findings.json + `inputs={target,cookie}`.) (+parity, tested.)
5. ✅ DONE Submission **package**: `core/package.py` `build_package(run_id)` — zips run dir (timeline+artifacts) + report.md + F3 `evidence/` into one bounty zip. `recon package <run_id>`. (+parity, tested.)

**F4 COMPLETE (all 5 steps) 2026-07-03.** JARVIS 422/0/9, recon 36/36, 0 flips. Possible follow-ups: JARVIS chat-intent + HUD download for replay/package; per-step replay for more stages; richer per-event `inputs` if finer replay granularity needed.

## Guardrails
- Timeline immutable + `schema_version` (bump when the event shape grows).
- Recorder must never break the pipeline — wrap in try/except, degrade silently.
- Artifacts written under `data/runs/` (gitignored), not the repo.
- friday-recon parity from day one (shared `core/timeline.py`, port like F1/F3).
