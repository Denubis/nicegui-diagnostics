# 00 — Vision

## One-sentence pitch

A standalone, MIT-licensed PyPI package providing the runtime diagnostics
endpoint and `ui.diagnostics_view()` element from upstream draft
[zauberzeug/nicegui#5867](https://github.com/zauberzeug/nicegui/pull/5867),
plus five production-validated gap fills, installable alongside any
`nicegui>=3.10.0` without rebasing the upstream branch.

## What success looks like for v0.1

A consumer (e.g. PromptGrimoireTool) can replace their vendored
`src/promptgrimoire/diagnostics.py` with `pip install nicegui-diagnostics` and
two lines of glue:

```python
from nicegui import app, ui
from nicegui_diagnostics import install, on_before_restart

install(
    features=["tasks", "memory", "clients", "config", "stack_dump", "delta"],
    structlog_interval_s=30,
    memory_restart_threshold_mb=3000,
    auth=lambda req: req.user.is_admin,
)
on_before_restart.append(my_flush_workspaces)

ui.run()
```

…and lose nothing they had before (lag probe, AIMD compatibility, watchdog
emission, graceful shutdown), while gaining the 4 unresolved review fixes
from upstream PR #5867 (kwargs-forwarding mirror, composable sub-elements,
auth gating, `openapi.json` registration).

## Non-goals for v0.1

- Replacing or replicating the NiceGUI `User` testing fixture. We forward
  kwargs to `ui.run()` via `user_simulation(**run_kwargs)` as PR #5867 did.
- Shipping a full admission-gate as the default install. Admission is its own
  module (`nicegui_diagnostics.admission`) that consumes `event_loop_lag_ms`
  but is optional. Most consumers will not need it.
- Shipping a single built-in "Web Speed Debug Bar" as a coupled
  measurement-plus-display widget. The two halves are kept separable on
  principle — see "Decoupling measurement from display" below.
- A graphical built-in `ui.diagnostics_view()` that looks polished. v0.1 ships
  the upstream Log-element view as a known-deficient default; the composable
  sub-element API (review point #2) is the v0.2 carrot.

## Constraints that shape every design decision

Sourced from `docs/design/01-maintainer-constraints-5660.md`:

1. **Zero overhead when disabled** — module not imported, route not
   registered, no background tasks running when the consumer doesn't `install()`.
2. **Granular toggle** — `install(features=[...])` takes a list, not a bool, so
   that "memory only" or "config only" deployments are first-class.
3. **Auth gating by default** — `auth=` callable required for global scope;
   `client_id` in any URL treated as a secret. Default-deny remote access.
4. **Both shapes** — HTTP endpoint for live introspection AND
   structured-log emission on an interval for out-of-process consumers
   (journald / jq / alertmanager).
5. **Works when the loop is blocked** — gap #1 separate-thread HTTP server is
   the only way; an async handler hangs in exactly the case you most need
   diagnostics for.
6. **Composable extension** — `extra_collectors: list[Callable[[], dict]]`
   so PromptGrimoireTool can add `app_ws_registry`, `auth_registry_count`,
   etc. without forking.

## Decoupling measurement from display

Every visible probe in the package ships as **two artifacts that compose but
do not depend on each other**:

- A *measurement primitive* (e.g. `measure_ws_rtt_ms()`,
  `measure_event_loop_lag()`, `count_clients()`) — pure Python, returns a
  number or dict, writes to an `ObservableDict` metric bus.
- A *display element* (e.g. `ui.diagnostics.ws_rtt()`,
  `ui.diagnostics.event_loop_lag()`) — reads from a bus, renders a label /
  badge / chart.

The reasons this matters:

| Concern             | Why decoupling helps                                                                                                                |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Use case**        | A consumer running a Prometheus exporter needs the probes but no UI; a consumer running a kiosk needs the UI bound to its own bus.   |
| **User demographic**| End-users shouldn't see infra metrics; admins should. Same probe, two displays gated differently.                                    |
| **Security**        | `client_id` and engine.io session IDs are secrets; the display layer decides what to render and the probe layer doesn't have to know. |
| **Performance**     | A consumer can run the probes once per minute and the bus binding 60× per second, or vice versa, without restructuring.              |

This is also why the prior-art "Web Speed Debug Bar" (see
[`05-private-prior-art.md`](05-private-prior-art.md)) stays on the roadmap
as a **stretch goal** rather than a non-goal — when we ship it, it'll be the
composition of three existing decoupled probes plus a thin
`ui.diagnostics.web_speed_bar()` element, not a monolithic widget.

## Out of scope, possibly forever

- PySnooper-style line tracing, py-spy flamegraphs. Falko explicitly said
  these are too much for core; that applies to the extension package too.
- Sub-second sampling. Anything that costs more than ~1 ms per probe on a
  ~30s loop is wrong on principle.
- Persistent storage of snapshot history. Snapshot history belongs in the
  consumer's metrics store (Prometheus, structlog → journald, whatever).
  The package emits; downstream collects.
