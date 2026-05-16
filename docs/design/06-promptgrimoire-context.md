# 06 — PromptGrimoireTool context

`nicegui-diagnostics` exists because [PromptGrimoireTool] (PG) needs it.
PG is the production consumer that vendored upstream PR #5867's collection
function, extended it with five gaps' worth of additions, learned what
worked under fire, and authored the gap-list this package implements.

This document captures what PG does, what it has learned, and what shape
that imposes on the package.

[PromptGrimoireTool]: https://github.com/MQFacultyOfArts/PromptGrimoireTool

## What PromptGrimoireTool is

A Macquarie University collaborative web app for prompt iteration and
annotation in educational contexts. Students import AI conversation
transcripts (Claude, ChatGPT, etc.) and collaboratively annotate them in
real time.

Stack: **NiceGUI 3.9.0 / Python 3.14 single-process, PostgreSQL+PgBouncer,
pycrdt (Yjs/Rust FFI), Stytch auth**, deployed to a 16-CPU / 32 GB
DigitalOcean box, targeted at ~1,800 concurrent classroom users.

Maintainer: [@Denubis](https://github.com/Denubis) (Brian Ballsun-Stanton).

## How PG uses diagnostics today

### 1. AIMD admission gate (`admission.py`)

PG runs an Additive-Increase Multiplicative-Decrease gate keyed off the
`event_loop_lag_ms` field from the snapshot. Cap halves when lag > 50 ms,
additive `+batch_size` when lag < 10 ms, hysteresis band in between.

The gate hooks into the existing 30 s diagnostic loop rather than spawning
a new background task — that's why the diagnostic emission cadence and the
admission cycle share state.

**Implication for the package:** `event_loop_lag_ms` must be a stable,
reliable field; consumers may build feedback loops against it. Don't change
the units silently. Don't add jitter without disclosure. (Spec gap #4
delta-mode helps here: a downstream gate can read both current and delta
from a single endpoint.)

### 2. Memory-threshold graceful restart (`graceful_memory_shutdown`)

When RSS exceeds 3 GB, PG triggers a controlled restart:

1. Flush CRDT state to disk
2. Persist dirty workspaces
3. Clear admission state
4. Navigate active clients to `/restarting`
5. Invalidate sessions
6. `SystemExit(75)` — systemd's `Restart=on-failure` picks it up

The exit code 75 is deliberate ("temp failure", systemd-identifiable).

**Implication for the package:** ship the threshold + ordered shutdown as
a sub-module (`restart.py`), but the ordering is application-specific.
Provide a `on_before_restart: list[Callable]` hook so PG can register its
flushers without us hardcoding their app shape.

### 3. External watchdog (`deploy/lag-watchdog.sh`)

A bash script under systemd that tails `journalctl -u promptgrimoire -f |
jq`, filters for `memory_diagnostic` events, and triggers restarts on
three rules:
- CRITICAL `>1000 ms` → instant restart
- WARN `>100 ms` × 2 strikes → escalation
- MASS_DISCONNECT (>50% user drop) → restart

Captures `collect-telemetry.sh` tarball before restart so log rotation
can't clobber the evidence.

**Implication for the package:** the structlog emission MUST happen even
when the HTTP endpoint can't be reached. An async handler fails the
watchdog use case — the watchdog needs the *structured log event* on a
known interval. Hence the `structlog_interval_s` parameter on `install()`.

### 4. Dev / chaos endpoints (`dev_endpoints.py`)

`POST /api/dev/block-loop?ms=300` synchronously sleeps the loop, schedules
the lag-probe via `call_soon` first so the same call measures the actual
freeze, then runs a live AIMD cycle and returns `cap_before` / `cap_after`.

**Implication for the package:** ship `block-loop` as a optional
sub-module behind a separate explicit opt-in
(`install(enable_dev_endpoints=True)`). Useful for E2E AIMD testing and
for demonstrating the stack-dump endpoint actually works under loop block.

## What the package learns from PG

| Lesson from PG                                                                  | Reflected in package design                                          |
| ------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Lag is *real*, not theoretical — admission gates work and are needed            | `event_loop_lag_ms` is a stable field, never silently changed       |
| Memory leaks happen and the diagnostic is the evidence base                     | All fields per [04-leak-pr-provenance.md](04-leak-pr-provenance.md) |
| External watchdogs need structured-log emission on a known interval             | `structlog_interval_s` parameter; emission is decoupled from HTTP   |
| Application-specific fields are essential (`app_ws_registry`, etc.)             | `register_collector()` extension point                              |
| Vendor-and-patch is painful when upstream churns                                 | Pin floor `nicegui>=3.10.0`, no ceiling                              |
| `on_disconnect` semantics surprised us                                          | Gap 3 lifecycle counters split disconnect from delete                |
| Daemon-thread watchdogs die under `process.terminate()`                          | Gap 1 stack-dump on a *foreground* thread with a HTTP server         |

## What PG migrating to the package looks like

```python
# before -- vendored module
from promptgrimoire.diagnostics import collect_snapshot
from promptgrimoire.admission import init_admission

# after -- pypi package + PG-specific glue
from nicegui_diagnostics import install, register_collector
from nicegui_diagnostics.admission import init_admission  # optional sub-module

install(
    features=["tasks", "memory", "clients+", "config", "stack_dump", "delta"],
    structlog_interval_s=30,
    memory_restart_threshold_mb=3000,
    auth=is_admin,
    on_before_restart=[flush_crdt, persist_dirty_workspaces, admission_clear],
)
register_collector("app_ws", collect_app_ws_metrics)
register_collector("admission", lambda: admission_state.snapshot())

init_admission(...)
ui.run()
```

The cost of migration is small (the package mirrors PG's existing call
shape), and the win is: PG stops carrying ~363 LOC of vendored
diagnostics, picks up gap-1 stack dumps and gap-4 delta mode "for free",
and inherits security/CVE fixes from the published package.

## Anti-pattern guard: what the package will NOT take from PG

- The CRDT-flushing logic. App-specific.
- The Stytch auth assumption. App-specific.
- The PgBouncer connection pool integration. App-specific.
- The `dict.pop(...)` hack to bypass `ObservableDict.on_change`. That's a
  PG-specific workaround for a PG-specific race; calling it out in the PG
  README is correct, but we are not going to take it as a package
  invariant.

## See also

- [`reference/promptgrimoire/diagnostics.py`](../../reference/promptgrimoire/diagnostics.py) —
  the actual 363-line vendored copy
- [`reference/promptgrimoire/2026-02-20-diagnostics-spec-gaps.md`](../../reference/promptgrimoire/2026-02-20-diagnostics-spec-gaps.md) —
  the canonical gap list
- [`reference/promptgrimoire/2026-03-30-lag-admission-gate.md`](../../reference/promptgrimoire/2026-03-30-lag-admission-gate.md) —
  AIMD design
- [`reference/promptgrimoire/lag-watchdog.sh`](../../reference/promptgrimoire/lag-watchdog.sh) —
  the bash watchdog
