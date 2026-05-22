# nicegui-diagnostics

Last verified: 2026-05-22

Standalone PyPI package porting NiceGUI PR #5867 diagnostics + five production-validated spec gaps from PromptGrimoireTool. Staging repo for Claude-Claude collaboration between @Denubis and @evnchn.

## Status

**Pre-alpha, scaffolding only.** `src/` is empty. Design docs in `docs/design/` are the source of truth for v0.1 scope. Project board: https://github.com/orgs/evnchn-nicegui/projects/1

This repo was bootstrapped by evnchn's Claude on 2026-05-16 (single commit `c62c1ba`) with Brian's Claude as the intended contributor. Both human maintainers have explicitly authorised the agent-to-agent workflow, but **architectural decisions require human checkpoints**. See "Working with humans" below.

## Tech stack

- Python 3.10+ (floor; target 3.10–3.13)
- `nicegui>=3.10.0` (floor only, no ceiling — see `docs/design/04-leak-pr-provenance.md`)
- Hatchling build backend
- Optional: `structlog>=24.0` for the interval emitter
- Dev: pytest, pytest-asyncio (auto mode), ruff (line-length 120), mypy

## Commands

```bash
uv sync                          # install (will pull nicegui>=3.10.0)
uv run pytest                    # tests (none yet)
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
uv build                         # sdist + wheel
```

## Project layout

| Path | Purpose |
|------|---------|
| `src/nicegui_diagnostics/` | The package itself. Currently empty scaffold. Submodule layout planned in `docs/design/02-api-surface.md` |
| `docs/design/00-vision.md` … `06-promptgrimoire-context.md` | Seven design docs synthesising upstream + PG + private prior-art inputs. Read these before changing scope |
| `reference/upstream-pr-5867/` | Vendored PR #5867 source at commit `0473e43`. Reference only — do not import |
| `reference/promptgrimoire/` | Vendored PG modules (diagnostics.py, admission.py, dev_endpoints.py, lag-watchdog.sh, two design docs). Reference only |
| `reference/private-prior-art/excerpts.py` | Three techniques sanitised from an evnchn private codebase, MIT-vendored: `measure_ws_rtt_ms`, `measure_js_burst_iterations`, `ClientCountHeartbeat` |
| `tests/` | Empty. Will use NiceGUI `User` fixture for in-process testing |

## Sibling repos (local development context)

These live next to this repo on Brian's machine and provide context the design docs don't capture:

| Path | Why it matters |
|------|----------------|
| `../nicegui/` | Fork of `zauberzeug/nicegui` (remotes: `fork` = Denubis, `upstream` = zauberzeug). Branch `diagnostics-5660` is the source of PR #5867. Worktrees under `.worktrees/` |
| `../nicegui-bug-repro/` | Contribution operations hub. Hosts the `contributing-to-nicegui` skill (`.claude/skills/contributing-to-nicegui/SKILL.md`) — load it for any upstream PR work. Also tracks merged PRs (#5805, #5806) and an in-flight contextvar leak investigation (bug 3) |
| `../PromptGrimoireTool/` | Production NiceGUI consumer that owns the spec-gaps doc. Has ~17 active worktrees under `.worktrees/`, several perf-related: `nicegui-perf-investigation`, `nicegui-perf-a1-a2`, `horizontal-scaling-466`, `reduce-log-noise`. Investigations to read for context: `docs/postmortems/2026-03-22-workspace-performance-377.md`, `docs/investigations/2026-03-27-memory-leak-434.md`, `docs/design-plans/2026-03-30-lag-admission-gate.md` |

## Design centre: the bus

**Load-bearing framing decision, session 2026-05-22.** Resolves an internal disagreement that the design docs don't yet reflect.

The bus (an `ObservableDict` metric bus, per `docs/design/02-api-surface.md` and `05-private-prior-art.md`) is the **design centre of the package**. Snapshots, counters, invariants, identity strips, lag HUDs, and any future composition (the v0.2 "Web Speed Debug Bar") are all nodes that read or write keys on the bus.

The justification for the bus is **live HUD during reproduction** — the reproduce-watch-iterate debugging loop. A snapshot-every-5-min log can't catch a sub-second identity cross or a transient outbox stall; per-render bus binding can. This is distinct from production monitoring (which is what PG's existing structlog + watchdog setup serves).

**What didn't win and why:**

- Earlier framing pitched "invariant probes" as the primary primitive (ConsistencyProbe-as-architecture). An ACH audit (see session 2026-05-22 transcript) ranked "snapshots primary, invariants as composition" higher. Falko's #5660 want-list, Evan's prior-art, and PG's existing consumer all favour snapshots. Invariants are *one valuable composition pattern* enabled by the bus — they catch bug-3-class issues (transient identity leakage) and the #5804 outbox-drain class. They are not the primitive.
- `ConsistencyProbe` as a named primitive is v0.2 thinking, not a v0.1 architectural commitment.

**Implication for v0.1:** ship the bus plumbing (`ObservableDict` singleton + helper for additional buses), ship snapshots/counters/lag/memory probes that write to it, ship at least one composed invariant probe (the contextvar-identity strip from PG bug 3) as a demo and a real catch.

## v0.1 scope

Per the project board, P0 lane is 13 items:

- 4 ports of PR #5867 (collect_snapshot, /_nicegui/diagnostics endpoint with auth, ui.diagnostics_view legacy element, user_simulation kwargs forwarding)
- 3 spec gaps (Gap 1 stack dump on separate thread, Gap 2 task age, Gap 4 delta mode)
- Structlog interval emitter (the watchdog half)
- 4 review-point fixes from PR #5867 (kwargs mirror, composable sub-elements, auth gating, openapi.json registration)
- v0.1.0 release on PyPI

P1 lane (5 items) and P2 lane (2 items) are explicit deferrals.

## Constraints

- **Do NOT create issues, PRs, or releases on `zauberzeug/nicegui` without explicit human approval.** Same constraint as `../nicegui-bug-repro/CLAUDE.md`.
- **Do NOT push to `evnchn-nicegui/nicegui-diagnostics` without write access.** Write access not yet accepted. Current default: fork-and-PR or local-only work. If write access lands, push to topic branches, never `main`.
- **Do NOT vendor more code from evnchn private repos without authorisation.** The three techniques in `reference/private-prior-art/` are the agreed scope.
- **Match the contributing-to-nicegui skill standards** for any code that might end up upstream: autopep8 120-char, single quotes Python, f-strings, never `asyncio.create_task()` (use `background_tasks.create(..., name=...)`).

## Working with humans

Brian (Denubis) alt-tabs heavily between sessions. Practical implications, learnt from session 2026-05-22:

- **Small chunks.** One decision per turn. Don't dump multi-paragraph option trees when intent is fuzzy.
- **One pointed question.** Functional decomposition per Brian's global CLAUDE.md — surface intent on each sub-goal before bundling.
- **Don't pad with examples.** Three strong examples beat eight with weak ones (peer-review caught this as a pattern-level finding).
- **"Mate" + swearing = frustration signal.** Read it as "I've context-switched and you're not making it easy."

Evan (evnchn) reviews after his Claude posts on his behalf. His comments are explicitly marked. Architectural choices made by his Claude are not the same as choices Evan has deliberated — flag the distinction when relying on them.

## Gotchas

- **Gap 5 (engineio session count)** reads `core.sio.eio.sockets`, a third-party private attribute. Wrap defensively; degrade to `None` with a one-time warning if the attribute moves. This is on the v0.1 P1 list, not P0.
- **`stack_dump_port=9999` default** is collision-prone. PG runs on 8080, lag-admission contemplates 8081, the same boxes run other services. Either pick a free port at install time (`socket.bind(("", 0))`) or require an explicit port with no default.
- **Private prior-art was removed from production after ~5 months.** The README in `reference/private-prior-art/` reads this as "ship opt-in." Could equally mean "the probes weren't worth their runtime cost." Ask Evan before assuming the techniques are safe to ship-as-default.
- **PG migration is non-trivial.** `06-promptgrimoire-context.md` shows a 6-line drop-in; reality has PG's `diagnostics.py` entangled with `pages/restart.py`, `auth/client_registry`, and a FilePersistentDict sync-write hack. Agents will handle the refactor when the package is ready; the example in the design doc is aspirational.
- **Bug 3 (PG contextvar cross-user leak)** is unreproduced for 6+ weeks. The contextvar-identity invariant probe (see "Design centre" above) is the first real attempt at catching it live. Ship it as a v0.1 demo even if the architecture for invariant-probes-as-composition isn't fully built out.
