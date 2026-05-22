# Initial build session — 2026-05-22

Paste-ready prompt for the first implementation session. Working directory:
`/home/brian/people/Brian/nicegui-diagnostics/`. CLAUDE.md auto-loads.

---

## Prompt for a fresh Claude Code session

> Read `CLAUDE.md` and `docs/design/00-vision.md`, `02-api-surface.md`,
> `03-spec-gaps.md`, `06-promptgrimoire-context.md`, `07-pg-monkeypatch-inventory.md`
> first. Then build the v0.1 foundation — the minimum that makes every
> subsequent P0 item composable.
>
> **Scope for this session (one PR):**
>
> 1. `src/nicegui_diagnostics/_bus.py` — `MetricBus` thin wrapper around
>    `nicegui.observables.ObservableDict`, module-level singleton accessor
>    `get_bus()`, plus public `make_metric_bus()` helper for downstream
>    consumers that want their own bus (per design doc 02-api-surface
>    "decoupling principle"). Single-writer-per-key contract; concurrent
>    writes to the same key are last-writer-wins (document this).
>
> 2. `src/nicegui_diagnostics/__init__.py` — public surface for v0.1:
>    - `install(features=None, structlog_interval_s=0, auth=None,
>      extra_collectors=None)` — idempotent setup; raises
>      `RuntimeError("nicegui-diagnostics already installed")` on double-call.
>      When `install()` has not been called, importing the package must do
>      nothing observable (no route registration, no threads, no background
>      tasks). The "truly opt-in" constraint from
>      `01-maintainer-constraints-5660.md` is load-bearing.
>    - `collect_snapshot(client_id=None, verbose=False) -> dict` — composes
>      enabled probes into a single snapshot dict. Returns `{}` if
>      `install()` was never called.
>    - `register_collector(name: str, callable: Callable[[], dict]) -> None`
>      — extension hook. Replaces PG's `sys.modules` lazy-accessor pattern
>      (see `docs/design/07-pg-monkeypatch-inventory.md` §3). Collector
>      must return a dict, run synchronously in <1 ms, get a fresh
>      snapshot context per call.
>    - `uninstall() -> None` — reverse `install()`, restore any wrapped
>      callables, clear the bus. Required for clean test teardown.
>
> 3. `src/nicegui_diagnostics/probes/tasks.py` — per-qualname asyncio task
>    grouping (port from `reference/upstream-pr-5867/diagnostics.py` lines
>    22–40, `_collect_task_summary`). Write to bus key
>    `"asyncio_tasks"`; return the dict from `collect()`.
>
> 4. `src/nicegui_diagnostics/probes/memory.py` — cross-platform memory
>    probe (port from `reference/upstream-pr-5867/diagnostics.py` lines
>    43–70, `_collect_memory`). Write to bus key `"memory"`; return the
>    dict from `collect()`. Keep the Linux/macOS branching and the
>    `/proc/self/status` fallback; both originate in PR #5867.
>
> 5. `tests/test_install.py` — install idempotency, double-install raises,
>    `uninstall()` restores baseline, import without install has zero
>    side effects.
>
> 6. `tests/test_collect_snapshot.py` — snapshot returns dict with
>    `asyncio_tasks` and `memory` keys when those features are enabled;
>    `register_collector` keys land in the snapshot; missing-feature keys
>    don't appear.
>
> **Out of scope for this session:**
>
> - HTTP endpoint (`/_nicegui/diagnostics`) — needs review-point-4 pydantic
>   model decision; defer to next session.
> - `ui.diagnostics_view()` element — depends on bus binding patterns;
>   defer.
> - Stack-dump probe (gap 1) — separate concern, separate session.
> - Structlog interval emitter — depends on `collect_snapshot()` being
>   stable; next session.
> - Any probe that wraps NiceGUI internals (`Client.delete` lifecycle,
>   loop watchdog) — needs install/uninstall semantics nailed down first.
>
> **Architecture (do not redesign — read the docs):**
>
> The bus is the design centre, per CLAUDE.md "Design centre: the bus."
> Every probe writes to it; every display element reads from it. Snapshots
> are a "collect all current bus state into a dict" operation. Invariant
> probes are deferred to v0.2 — do not build a `ConsistencyProbe` primitive
> in this session.
>
> **Quality bar:**
>
> - `uv run pre-commit run --all-files` passes before any commit
>   (ruff-check, ruff-format, mypy, complexipy ≤15, gitleaks, whitespace)
> - Tests run via `uv run pytest`
> - Functions stay under complexity 15 (complexipy gate); if you blow it,
>   refactor rather than excluding the file
> - Match the PG/NiceGUI house style: f-strings, single quotes Python,
>   no `asyncio.create_task` (none should be needed in this session)
> - Comment only the WHY where non-obvious — naming carries the WHAT
>
> **Work-flow:**
>
> - Branch off `main` (already on `setup/initial-environment` once this
>   PR lands; check `git branch -a` for the right base)
> - Topic branch name: `build/foundation-bus-and-snapshot`
> - One commit per logical piece (bus → install/snapshot → probes →
>   tests), or one commit per file is also fine
> - Push to `origin` (which points at `Denubis/nicegui-diagnostics` fork)
> - Open PR against `evnchn-nicegui/nicegui-diagnostics` `main`
> - Commit trailer: `Co-authored-by: Claude Opus 4.7 <noreply@anthropic.com>`
> - Halt and ask the human (Brian) at any architectural fork, any
>   uncertainty about the upstream design intent, or any compliance
>   concern. Do not invent design beyond what the docs specify.
>
> **Supervisor (the agent that briefed you):** will review your PR, push
> back on anything that drifts from the bus-centric framing or the docs,
> and answer questions if you tag for input.

---

## Operating notes (not for the next session, for Brian)

- This session prompt is intentionally narrow. The package's full P0 lane
  is 13 items; this kicks off the first 1–2. The remaining items each get
  their own session prompt under `docs/sessions/`.
- If the next session blows past scope (e.g. drafts the HTTP endpoint or
  builds a stack-dump probe), reject the PR with a pointer back to
  "out of scope" above. Scope discipline is what makes the v0.1 cut
  achievable.
- The supervisor pattern: Brian's main session (this one) reads the PR,
  flags issues, asks pointed questions on the PR thread, and merges when
  the bar is met. The build session does not have access to this
  supervisor's chat history — only what's in `CLAUDE.md` and the design
  docs.
