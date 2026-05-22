# nicegui-diagnostics

Last verified: 2026-05-22

Standalone PyPI package porting NiceGUI PR #5867 diagnostics + five production-validated spec gaps from PromptGrimoireTool.

## Status

**Pre-alpha, scaffolding only.** `src/` is empty. Design docs in `docs/design/` are the source of truth for v0.1 scope. Project board: https://github.com/orgs/evnchn-nicegui/projects/1

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

## Design centre: the bus

The bus (an `ObservableDict` metric bus, per `docs/design/02-api-surface.md` and `05-private-prior-art.md`) is the **design centre of the package**. Snapshots, counters, invariants, identity strips, lag HUDs, and any future composition (the v0.2 "Web Speed Debug Bar") are all nodes that read or write keys on the bus.

The justification for the bus is **live HUD during reproduction** — the reproduce-watch-iterate debugging loop. A snapshot-every-5-min log can't catch a sub-second identity cross or a transient outbox stall; per-render bus binding can. This is distinct from production monitoring (which is what PG's existing structlog + watchdog setup serves).

**What didn't win and why:**

- An earlier framing pitched "invariant probes" as the primary primitive (ConsistencyProbe-as-architecture). Falko's #5660 want-list, Evan's prior-art, and the production consumer pattern from PromptGrimoireTool all favour snapshots. Invariants are *one valuable composition pattern* enabled by the bus — they catch transient identity leakage (the kind that drove the contextvar-leak class of bugs) and the #5804 outbox-drain class. They are not the primitive.
- `ConsistencyProbe` as a named primitive is v0.2 thinking, not a v0.1 architectural commitment.

**Implication for v0.1:** ship the bus plumbing (`ObservableDict` singleton + helper for additional buses), ship snapshots/counters/lag/memory probes that write to it, ship at least one composed invariant probe (a contextvar-identity strip) as a demo of the composition pattern.

## v0.1 scope

Per the project board, P0 lane is 13 items:

- 4 ports of PR #5867 (collect_snapshot, /_nicegui/diagnostics endpoint with auth, ui.diagnostics_view legacy element, user_simulation kwargs forwarding)
- 3 spec gaps (Gap 1 stack dump on separate thread, Gap 2 task age, Gap 4 delta mode)
- Structlog interval emitter (the watchdog half)
- 4 review-point fixes from PR #5867 (kwargs mirror, composable sub-elements, auth gating, openapi.json registration)
- v0.1.0 release on PyPI

P1 lane (5 items) and P2 lane (2 items) are explicit deferrals.

## Constraints

- **Do NOT vendor additional source from upstream private repos.** The MIT-vendored material in `reference/private-prior-art/` is the agreed scope; any additions require authorisation from the original author.
- **Upstream-bound code follows NiceGUI house style:** autopep8 with 120-char line length, single quotes in Python, double quotes in JavaScript, f-strings, `background_tasks.create(..., name=...)` (never bare `asyncio.create_task()`), `contextlib.suppress(...)` over try-except-pass, `# NOTE:` prefix for non-obvious implementation details. Catch `ImportError` not `ModuleNotFoundError` for optional deps.

## Gotchas

- **Gap 5 (engineio session count)** reads `core.sio.eio.sockets`, a third-party private attribute. Wrap defensively; degrade to `None` with a one-time warning if the attribute moves. This is on the v0.1 P1 list, not P0.
- **`stack_dump_port=9999` default** is collision-prone. PG runs on 8080, lag-admission contemplates 8081, the same boxes run other services. Either pick a free port at install time (`socket.bind(("", 0))`) or require an explicit port with no default.
- **Private prior-art was removed from production after ~5 months.** The README in `reference/private-prior-art/` reads this as "ship opt-in." Could equally mean "the probes weren't worth their runtime cost." Ask Evan before assuming the techniques are safe to ship-as-default.
- **PG migration is non-trivial.** `06-promptgrimoire-context.md` shows a 6-line drop-in; reality has PG's `diagnostics.py` entangled with `pages/restart.py`, `auth/client_registry`, and a FilePersistentDict sync-write hack. Agents will handle the refactor when the package is ready; the example in the design doc is aspirational.
- **Contextvar-leak-class bugs are transient and hard to reproduce.** The contextvar-identity invariant probe (see "Design centre" above) is the v0.1 demo of why per-render bus binding earns its place: it can catch identity-source disagreement the moment it happens, where a snapshot-every-N-seconds log cannot. Ship it even if the broader invariant-probe API isn't fully built out — the demo carries the argument.
