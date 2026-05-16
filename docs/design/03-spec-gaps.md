# 03 — The 5 spec gaps

Verbatim and analysis of the gap list authored by PromptGrimoireTool's
maintainer in [`reference/promptgrimoire/2026-02-20-diagnostics-spec-gaps.md`](../../reference/promptgrimoire/2026-02-20-diagnostics-spec-gaps.md),
which became the primary requirements source for this package. Priority
ordering by *investigation-time saved* is the maintainer's own (file:332-338).

For each gap: what upstream PR #5867 ships, what's missing, the production
incident that revealed the gap, and our planned implementation.

## Gap 1 — On-demand thread stack dump (P0)

**What's in PR #5867:** an async `/_nicegui/diagnostics` handler that returns
a per-qualname task summary.

**What's missing:** when the event loop is blocked, the async handler hangs.
You cannot debug a blocked-loop incident with a tool that requires the loop
to respond.

**Production evidence (file:30):** "Phase 3 of the investigation was **five
consecutive failed attempts** at capturing thread stacks during event loop
blocks." Root cause: a daemon-thread watchdog gets killed by
`process.terminate()` before any disk write completes.

**Critical subtlety (file:60):** "This endpoint is an async handler running
on the event loop. If the event loop is blocked, the request itself will
hang."

**Our implementation:** a small `http.server.HTTPServer` on a background
thread, on a configurable port (default 9999). Returns
`sys._current_frames()` formatted as text. Localhost-only by default.

This is the **single biggest investigation-time saver** in the gap list
(maintainer's own assessment). Therefore: P0, ships in v0.1.

```python
# Sketch -- the full impl will be in src/nicegui_diagnostics/probes/stack_dump.py
import http.server, threading, sys, traceback

def _start_stack_dump_server(port: int = 9999) -> threading.Thread:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/stacks":
                self.send_error(404); return
            frames = sys._current_frames()
            body = "\n\n".join(
                f"=== thread {tid} ===\n{''.join(traceback.format_stack(frame))}"
                for tid, frame in frames.items()
            ).encode()
            self.send_response(200); self.end_headers(); self.wfile.write(body)
    srv = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return t
```

## Gap 2 — Task age (`oldest_age_s`) (P0)

**What's in PR #5867:** per-qualname task counts (e.g. `"Event.wait": 19`).

**What's missing:** counts alone are ambiguous. A `Event.wait` task that
lives for 5 ms (waiting on a normal page render) looks identical to a
`Event.wait` task that's been alive for 142 s (leaked from `page.py`'s
race-loser branch — the root cause of [#5803]/[#5806]).

[#5803]: https://github.com/zauberzeug/nicegui/issues/5803
[#5806]: https://github.com/zauberzeug/nicegui/pull/5806

**Production evidence (file:155-160):** "Phase 10 found 19 `Event.wait`
tasks accumulated. The qualname grouping showed *what* they were, but not
*how long they'd been alive*. Normal `Event.wait` tasks resolve in
milliseconds. Leaked ones from `page.py` live forever."

**Target output shape (file:206):**

```json
{
  "Event.wait": {"count": 19, "oldest_age_s": 142.3}
}
```

"No source reading required" — the maintainer's framing.

**Our implementation:** instrument `nicegui.background_tasks.create()` to
stamp a `_birth_time` on each task, drop it in a `done_callback`. We don't
monkey-patch `nicegui.*` on import (per
[constraint](01-maintainer-constraints-5660.md)); instead the `probes/tasks.py`
module wraps `background_tasks.create` lazily on `install()` if the
`"tasks"` feature is enabled.

## Gap 3 — Client lifecycle event counters (P1)

**What's in PR #5867:** point-in-time `clients_total`, `clients_connected`.

**What's missing:** transition counters. `on_disconnect` fires on *every*
socket disconnect including temporary reconnects during page navigation —
that's the surprise PG learned the hard way (file:224): "Our cleanup code
was in `on_disconnect`, running heavy operations on every reconnect — not
just final departure."

**Production evidence:** moved cleanup from `on_disconnect` to `on_delete`
after the counter ratio `disconnects: 47 / deletes: 12` made the bug
obvious. Without the counters, the misuse looks correct from any
point-in-time snapshot.

**Target output (file:236-244):**

```json
{
  "lifecycle": {
    "connects_total": 124,
    "disconnects_total": 47,
    "reconnects_total": 32,
    "deletes_total": 12,
    "active_reconnect_windows": 4
  }
}
```

**Our implementation:** register `app.on_connect` / `app.on_disconnect` /
`Client.on_delete` (if the public API allows) in `probes/lifecycle.py`.
Counters are monotonic since `install()` time. Lives in `"clients+"`
feature flag (additive to `"clients"`).

## Gap 4 — Delta mode (`?delta=true`) (P0)

**What's in PR #5867:** snapshot is a point-in-time object. To detect
accumulation, the caller must remember a previous snapshot and diff fields
themselves.

**What's missing:** built-in delta calculation against the previous query.
The accumulation pattern (every delta positive, nothing returning to zero)
is the leak signal that uniquely identifies [#5930]/[#5931].

[#5930]: https://github.com/zauberzeug/nicegui/issues/5930
[#5931]: https://github.com/zauberzeug/nicegui/pull/5931

**Production evidence (file:275):** "The investigation had to manually hit
`/api/test/diagnostics` after each test and build a comparison table by
hand."

**Target output:**

```json
{
  "current": {"asyncio_tasks_total": 53, "clients_total": 7, ...},
  "delta": {"asyncio_tasks_total": "+11", "clients_total": "0", ...},
  "since_last_query_s": 4.81
}
```

**Our implementation:** `probes/delta.py` keeps a single
`_previous_snapshot` dict in module scope; `?delta=true` triggers
recursive numeric diff with sign-preserving string formatting. The "every
delta positive" pattern is enough on its own to flag a leak in a CI run.

## Gap 5 — engine.io / socket.io session counts (P1)

**What's in PR #5867:** NiceGUI client count.

**What's missing:** the engine.io session count. A discrepancy
(`engineio_sessions: 8, nicegui_clients: 5`) flags **orphan sockets** —
WebSocket receive tasks whose owning client has been deleted but the
socket itself wasn't released. This is exactly the pathology that
[#5803]/[#5806] addressed at the *task* level; the socket level is the
corresponding next-layer check.

**Production evidence (file:313):** "The cleanup endpoint had to iterate
`core.sio.eio.sockets` to disconnect orphan engine.io sessions —
WebSocket receive tasks from connections whose NiceGUI client was already
deleted."

**Target output:**

```json
{
  "engineio_sessions": 8,
  "nicegui_clients": 5,
  "orphan_sockets_estimate": 3
}
```

**Our implementation:** `probes/eio.py` reads
`nicegui.core.sio.eio.sockets` defensively (it's a private attribute;
we'll degrade to `None` if the attribute moves) and computes the
discrepancy. Lives in the `"eio"` feature flag.

## Maintainer's priority ordering

Verbatim from `2026-02-20-diagnostics-spec-gaps.md` file:332-338:

> 1. Stack dump → 2. Task age → 3. Lifecycle counters → 4. Delta mode → 5. Socket.io counts

We follow this exactly. Gap 1, 2, and 4 ship in v0.1 (P0). Gap 3 and 5
ship in v0.2 (P1) — they need lifecycle hooks and engine.io access that
benefit from a second pass on the framework integration surface.
