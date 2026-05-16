# 02 — Proposed public API surface

Status: **proposal, not yet implemented.** This document captures the
package's planned public surface, grading every shape choice against the
constraints in [`01-maintainer-constraints-5660.md`](01-maintainer-constraints-5660.md)
and the decoupling principle in [`00-vision.md`](00-vision.md).

## Top-level entry point

```python
from nicegui_diagnostics import install

install(
    features=["tasks", "memory", "clients", "config", "stack_dump", "delta"],
    structlog_interval_s=30,            # 0 disables structlog emission
    memory_restart_threshold_mb=3000,   # None disables threshold restart
    auth=lambda req: req.user.is_admin, # required for any global-scope access
    extra_collectors=[my_collector],    # for app-specific fields
    stack_dump_port=9999,               # separate-thread HTTP server (gap 1)
    on_before_restart=[my_flusher],     # gracefully shut down side effects
)
```

`install()` MUST be called before `ui.run()`. Calling it twice raises
`RuntimeError("nicegui-diagnostics already installed")`. Calling it with
`features=[]` is allowed and silently no-ops every collector — useful in
test runs.

When `install()` is **not** called, the `nicegui_diagnostics` import has
zero runtime side effects (no route registration, no background tasks, no
heavy submodule import). This satisfies the
[#5660 maintainer constraint](01-maintainer-constraints-5660.md) "truly opt-in".

## Feature flags

| Flag           | What it enables                                              | Maps to upstream PR #5867 / PG gap |
| -------------- | ------------------------------------------------------------ | ---------------------------------- |
| `"tasks"`      | per-qualname task summary, oldest-age-per-group              | PR #5867 + PG gap 2                |
| `"memory"`     | `resource.getrusage` + `/proc/self/status` VmRSS scan        | PR #5867                           |
| `"clients"`    | per-client outbox depth + socket status                      | PR #5867                           |
| `"clients+"`   | adds lifecycle counters (connects/disconnects/...)           | PG gap 3                           |
| `"config"`     | `async_handlers`, transports, reconnect_timeout, ...         | PR #5867                           |
| `"stack_dump"` | separate-thread HTTP stack-dump server                       | PG gap 1                           |
| `"delta"`      | `?delta=true` query param for previous-vs-current diff       | PG gap 4                           |
| `"eio"`        | engine.io session vs NiceGUI client count                    | PG gap 5                           |
| `"js_rtt"`     | client-side `ui.run_javascript("1+1")` RTT probe             | Prior-art harvest                  |
| `"heartbeat"`  | client-count heartbeat dict + TTL purge                      | Prior-art harvest                  |

Note: `"clients+"` is additive — `features=["clients", "clients+"]` is the
same as `features=["clients+"]`. The two names exist because counts alone
(`"clients"`) is the minimum interesting subset and matches what PR #5867
ships out of the box.

## HTTP endpoint

`GET /_nicegui/diagnostics`

Query params (all optional):
- `client_id=<id>` — return verbose detail for one client (admin-only)
- `verbose=true` — include all-client detail (admin-only)
- `delta=true` — return current snapshot AND deltas vs previous query

Auth: the `auth=` callable from `install()` is invoked with the Starlette
`Request`. Default behaviour if no `auth=` given:
- non-verbose, no client_id, no delta → returns coarse counts
- ANY of `verbose=`, `client_id=`, `delta=` → 401

This addresses [evnchn review point #3](01-maintainer-constraints-5660.md#explicit-we-want-from-evnchn-review-round-blocking).

Stack-dump endpoint (separate-thread `http.server.HTTPServer`):

`GET http://localhost:<stack_dump_port>/stacks`

Auth: localhost-only by default. Returns `sys._current_frames()` formatted
text. The point of being on a separate thread on a different port is that
it works when the event loop is blocked — see PG gap 1.

## OpenAPI / pydantic response models

This addresses [evnchn review point #4](01-maintainer-constraints-5660.md#explicit-we-want-from-evnchn-review-round-blocking).

```python
class DiagnosticsSnapshot(pydantic.BaseModel):
    asyncio_tasks_total: int
    asyncio_tasks_by_qualname: dict[str, TaskGroup]
    memory: MemoryProbe
    clients_total: int
    clients_connected: int
    clients_by_id: dict[str, ClientDetail] | None = None  # verbose-only
    config: ServerConfig
    event_loop_lag_ms: float
    timestamp: datetime
    delta_from_previous_s: float | None = None
    delta: SnapshotDelta | None = None  # delta-mode only
```

The model is registered with FastAPI/Starlette **before** `ui.run()` is
called, so it lands in `openapi.json` for tool/LLM discovery.

## UI elements (composable, decoupled from probes)

This addresses [evnchn review point #2](01-maintainer-constraints-5660.md#explicit-we-want-from-evnchn-review-round-blocking).
PR #5867 ships one monolithic `ui.diagnostics_view()` Log element; we keep
it (under the legacy name) for compatibility and ship composable
sub-elements alongside.

```python
# Legacy / minimal — replicates PR #5867 behaviour
ui.diagnostics_view(scope="client", mode="append", interval=1.0)

# Composable — subscribe to specific bus keys
with ui.diagnostics.panel(scope="admin", auth=is_admin):
    ui.diagnostics.task_summary()
    ui.diagnostics.event_loop_lag()
    ui.diagnostics.memory_chart()
    ui.diagnostics.client_table()
    ui.diagnostics.ws_rtt()         # client-side JS probe display
    ui.diagnostics.web_speed_bar()  # v0.2+ stretch composition
```

Each sub-element reads from the package's internal `ObservableDict` metric
bus. Consumers can also instantiate them against their own bus.

## Pytest fixture forwarding

This addresses [evnchn review point #1](01-maintainer-constraints-5660.md#explicit-we-want-from-evnchn-review-round-blocking).

PR #5867 added `**run_kwargs: Any` to `user_simulation()` but didn't mirror
the API on the `user` pytest fixture. We document the fixture-level shape
that consumers should expect upstream to land:

```python
@pytest.fixture
async def user_with_diagnostics(user):
    user.ui_run_kwargs["diagnostics"] = True
    yield user
```

If `screen.ui_run_kwargs` lands upstream first, we re-export the same name
for parity. Filed as a separate concern from this package — the right home
is NiceGUI core, not us.

## Programmatic API for collectors

```python
from nicegui_diagnostics import collect_snapshot, register_collector

# pull a snapshot directly (e.g. from a /healthz endpoint)
snapshot: DiagnosticsSnapshot = collect_snapshot(client_id=None, verbose=False)

# register an app-specific collector
def my_collector() -> dict[str, Any]:
    return {"app_ws_registry": len(my_app.ws_registry)}

register_collector("app_ws", my_collector)
# next snapshot will include {"app_ws": {"app_ws_registry": 17}}
```

`register_collector()` is the primary extension point. PromptGrimoireTool
uses this to ship `app_ws_registry`, `app_ws_presence_workspaces`,
`auth_registry_count`, etc., without forking. The contract: the callable
returns a `dict[str, Any]` synchronously in <1 ms, runs in the snapshot
thread, and gets a fresh "snapshot context" per call.

## Sub-modules and what they own

```
nicegui_diagnostics/
├── __init__.py             install(), collect_snapshot(), register_collector()
├── api.py                  HTTP endpoint + pydantic models
├── auth.py                 default-deny auth helpers
├── probes/
│   ├── tasks.py            per-qualname grouping + oldest_age_s
│   ├── memory.py           resource.getrusage + /proc/self/status
│   ├── clients.py          counts + per-client detail
│   ├── lifecycle.py        connects/disconnects/reconnects/deletes counters
│   ├── config.py           server config snapshot
│   ├── stack_dump.py       separate-thread HTTPServer
│   ├── delta.py            delta-from-previous calculation
│   ├── eio.py              engine.io session counts
│   ├── event_loop_lag.py   measure_event_loop_lag()
│   ├── ws_rtt.py           ui.run_javascript("1+1") probe
│   └── heartbeat.py        client-count heartbeat dict
├── elements/
│   ├── diagnostics_view.py legacy monolithic Log view
│   ├── panel.py            ui.diagnostics.panel context manager
│   ├── task_summary.py     ui.diagnostics.task_summary()
│   ├── memory_chart.py     ui.diagnostics.memory_chart()
│   ├── ws_rtt.py           ui.diagnostics.ws_rtt() display
│   └── web_speed_bar.py    v0.2+ stretch composition
├── emitter.py              structlog interval emitter
├── restart.py              memory-threshold graceful restart (PG)
└── _bus.py                 internal ObservableDict singleton
```

Submodules under `probes/` and `elements/` are deliberately one-file-per-
feature so the feature flag → import path mapping is mechanical.

## What this API does NOT do

- It does NOT monkey-patch `nicegui.*` modules on import.
- It does NOT define routes when `install()` is not called.
- It does NOT depend on `psutil`, `structlog`, or any heavy optional.
  `structlog` is enabled if installed (`extras_require=["structlog"]`).
- It does NOT define an `admission` gate. That's a separate sub-module the
  consumer wires up themselves; see `docs/design/06-promptgrimoire-context.md`.
- It does NOT block the event loop in any probe. The slowest probe is
  `measure_event_loop_lag` itself, which is <1 ms on an idle loop.

## Stability and versioning

- `0.0.x`: pre-alpha, scaffolding only, API shape can change.
- `0.1.0`: first installable; freeze `install()`/`collect_snapshot()` signatures.
- `0.2.0+`: additive only on the public surface; no breaking changes.
- Pin floor stays `nicegui>=3.10.0`. We pin a *floor*, not a ceiling.
