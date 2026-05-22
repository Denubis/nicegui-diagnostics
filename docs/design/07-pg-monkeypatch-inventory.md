# 07 — PromptGrimoireTool monkeypatch inventory

What PG carries today that the v0.1 package needs to absorb so PG can drop it
on adoption. Inventoried from `MQFacultyOfArts/PromptGrimoireTool` `main` @
`5143d5e` on 2026-05-22.

**Brian's stated goal:** "have something that I can swap out for
PromptGrimoireTool's monkeypatches." This document is the gap list between
"PG today" and "PG with `pip install nicegui-diagnostics`."

## 1. `Client.delete` wrap for per-delete instrumentation

**Where:** `src/promptgrimoire/cli/e2e/_server_script.py:563-583`

```python
_orig_delete = _Client.delete
_delete_logger = structlog.get_logger("e2e.client_delete")

def _timed_delete(self):
    n_elements = len(self.elements) if hasattr(self, "elements") else -1
    t0 = _time.monotonic()
    _orig_delete(self)
    elapsed = _time.monotonic() - t0
    _delete_logger.debug("CLIENT_DELETE: id=%s elements=%d elapsed=%.3fs",
                         self.id[:8], n_elements, elapsed)

_Client.delete = _timed_delete  # type: ignore[assignment]
```

Currently E2E test-only. Same shape would be useful in production for the
memory-leak hunt (#434) where the cleanup time vs element count correlation
is the load-bearing signal.

**Package absorption (v0.1):** `probes/lifecycle.py` includes a clean wrap-
and-unwind of `Client.delete` driven by the `"clients+"` feature flag (the
gap 3 additive feature). The probe writes `{client_delete_elapsed_s,
client_delete_elements}` to the bus per call, contributes to
`deletes_total`, and unwinds the patch on uninstall (or on test teardown
via a context-manager API). No more bare `Client.delete = ...` assignment
at module scope.

**Replacement contract:**

```python
from nicegui_diagnostics import install
install(features=["clients+"], ...)  # wraps Client.delete cleanly
```

## 2. Out-of-process event-loop watchdog

**Where:** `src/promptgrimoire/cli/e2e/_server_script.py:520-555` plus the
`_watchdog_loop` thread setup.

PG runs a daemon thread that holds a reference to the running asyncio loop
and pings it on an interval. If the ping doesn't come back within a
threshold, the watchdog flags an event-loop block. The pattern is necessary
because `loop.set_debug(True)` is itself the *cause* of severe loop blocks
on Python 3.14 (linecache.checkcache on every task creation) — so PG
explicitly runs with debug OFF and uses the watchdog instead.

**Package absorption (v0.1):** This is the same problem space as Gap 1
(separate-thread HTTP server for stack dumps). The watchdog detects the
block; the stack-dump server captures evidence of what's blocking. They
compose:

- `probes/loop_watchdog.py` — daemon thread + ping loop; writes
  `event_loop_block_ms` to the bus and emits structlog
  `event_loop_block_detected` on threshold cross.
- `probes/stack_dump.py` — Gap 1's separate-thread HTTPServer; the
  watchdog can call it directly on detection, dumping `sys._current_frames()`
  to a configurable path (or making it available on the stack-dump port).

The package's value-add over PG's current code: composes the two probes
behind one feature flag, sets sane defaults, and ships a `restore()` /
context-manager for clean teardown so tests don't leave the daemon running.

**Replacement contract:**

```python
install(features=["loop_watchdog", "stack_dump"], ...)
```

## 3. `sys.modules` lazy accessor for app-state collection

**Where:** `src/promptgrimoire/pages/restart.py:48` (`_get_annotation_state`)
called from `src/promptgrimoire/diagnostics.py:90`.

PG's snapshot collector needs access to app-specific state held in modules
that haven't been imported when the diagnostic timer first fires. The lazy
accessor does `sys.modules.get("promptgrimoire.pages.annotation")` and
fishes out `workspace_presence` and `workspace_registry` if available.

This is not a NiceGUI monkeypatch but it's the same family — bolted-on
observability that exists because there's no proper hook to feed
application-specific fields into the diagnostic snapshot.

**Package absorption (v0.1):** Already in the API design. `register_collector(
name, callable)` is the public hook. PG's `_get_annotation_state` becomes:

```python
def _annotation_state_collector() -> dict[str, Any]:
    workspace_presence, workspace_registry = _get_annotation_state()  # local helper
    return {
        "app_ws_registry": len(workspace_registry._documents)
                           if workspace_registry else 0,
        "app_ws_presence_workspaces": len(workspace_presence),
        "app_ws_presence_clients": sum(len(v) for v in workspace_presence.values()),
    }

register_collector("annotation", _annotation_state_collector)
```

No `sys.modules` trick required — PG calls `register_collector` after its
app modules import, the package handles the rest.

## 4. (Not a patch, but in the same family) FilePersistentDict sync-write

**Where:** `src/promptgrimoire/diagnostics.py:175-197`
(`_invalidate_all_sessions`).

PG calls `dict.pop(user_storage, "auth_user", None)` to bypass NiceGUI's
`ObservableDict.on_change` hook, then writes the file synchronously to
guarantee survival across `systemctl restart`. This is an
`_invalidate_sessions` concern, not a diagnostics concern, but it's part
of the same `restart.py` shutdown path the package's `on_before_restart`
hook will replace.

**Package absorption:** `on_before_restart=[my_flusher]` callback list on
`install()` lets PG keep its own session-invalidation logic without the
package having to know about Stytch or PG's auth storage shape. The
`dict.pop` trick stays in PG's flusher; the package just guarantees the
flusher runs before the memory-threshold `SystemExit(75)` fires.

## Out of scope for the package (PG keeps these)

- The Stytch auth wiring — application-specific.
- The PgBouncer connection pool integration — application-specific.
- The CRDT (pycrdt) state flushing — application-specific. The package's
  `on_before_restart` hook accepts it as a callback; the package doesn't
  ship CRDT knowledge.
- The lag-watchdog bash script (`deploy/lag-watchdog.sh`) — this consumes
  the structlog `memory_diagnostic` event from journald. The package emits
  the event; the watchdog stays a PG deploy artifact.

## Migration shape

```python
# PG before — vendored ~363 LOC diagnostics.py + Client.delete monkeypatch
# + watchdog thread setup + sys.modules accessor.

# PG after:
from nicegui_diagnostics import install, register_collector

install(
    features=["tasks", "memory", "clients+", "config",
              "stack_dump", "loop_watchdog", "delta"],
    structlog_interval_s=30,
    memory_restart_threshold_mb=3000,
    auth=is_admin,
    on_before_restart=[flush_milkdown_to_crdt,
                       persist_dirty_workspaces,
                       admission_clear,
                       navigate_clients_to_restarting,
                       invalidate_all_sessions],
)
register_collector("annotation", _annotation_state_collector)
register_collector("admission",  lambda: admission_state.snapshot())
register_collector("auth_registry", lambda: {
    "auth_registry_clients": sum(len(c) for c in auth_registry.values()),
    "auth_registry_users":   sum(1 for c in auth_registry.values() if c),
})
```

Net delete from PG: `src/promptgrimoire/diagnostics.py` (363 LOC) +
`_Client.delete` monkeypatch (~25 LOC in `_server_script.py`) + watchdog
thread setup. PG keeps the bash watchdog and the application-specific
flushers.
