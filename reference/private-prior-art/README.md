# Private prior-art

Patterns drawn from one of @evnchn's private NiceGUI applications and
[`excerpts.py`](excerpts.py) — a sanitized, generalized vendored extract,
reproduced here with permission under the top-level MIT licence.

The source repository itself is not public; this directory contains only
what's needed to inform `nicegui-diagnostics` design.

## Why this matters

The private project ran real performance-diagnostics instrumentation for ~5
months in 2025, then removed it during a production-stability pass. The
removal was a "we don't need this in prod" decision, not a "this is buggy"
decision — so the patterns described below are presumed-working at the time
they were taken out.

The removal itself is the most useful data point: **the package must ship
opt-in by default**, so a maintainer can disable diagnostics by deleting one
line of config instead of deleting 100+ LOC of HUD code.

## Techniques worth harvesting

### 1. WebSocket round-trip latency probe via `ui.run_javascript("1+1", timeout=...)`

Cheapest event-loop-cost RTT probe in NiceGUI. Pattern in pseudocode:

```python
t0 = datetime.now()
await ui.run_javascript("1+1", timeout=10)
rtt_ms = (datetime.now() - t0).total_seconds() * 1000
```

Rendered in a HUD as `LAG:NNN` (3 digits) or `LAG NNNN` (saturated 4 digits
via `min(round(rtt_ms), 9999)`), color-banded at 100/500 ms. In real
production the 4-digit band was *regularly* hit, justifying the wide format
up front.

Complements the server-side `event_loop_lag_ms` probe: the JS probe sees
network + serialization + browser RAF time on top of loop wait.

### 2. Heartbeat dictionary for client count (catches what `on_disconnect` misses)

```python
last_alive: dict[str, datetime] = {}

@app.on_connect
def _(client): last_alive[client.id] = datetime.now()

@app.on_disconnect
def _(client): last_alive.pop(client.id, None)

ui.timer(5.0, lambda: _purge_stale(last_alive, stale_after=30))
```

Catches tab-killed / network-cut / lid-closed cases that NiceGUI's own
`on_disconnect` never fires for. Independent of (and complementary to) PR
#5867's `client.has_socket_connection` check.

### 3. `ObservableDict` as a reactive metric bus

```python
metrics = ObservableDict()

def update_cpu():
    metrics["cpu_percent"] = psutil.cpu_percent(interval=1)

# anywhere in the UI:
ui.label().bind_text_from(
    metrics, "cpu_percent",
    backward=lambda x: f"CPU:{min(round(x), 99):02d}%",
)
```

NiceGUI-native way to build a HUD without writing custom JS, SSE, or shared
state primitives. Worth considering as the in-page side of
`ui.diagnostics_view()` once review point #2 (composable sub-elements) is
addressed.

### Honorable mention — fair-share scheduler

`time_to_sleep = EXPECTED_TIME_PERIOD / queue_size`: N clients share a 10 s
budget instead of each independently saturating the loop. Distinct from
PromptGrimoireTool's AIMD admission gate, which gates *entry*; this gates
*per-tick work*. Probably out of scope for v0.1 of the diagnostics package
but worth recording.

## Stretch goal: composed "Web Speed Debug Bar"

The opacity-50 `LAG / SPD / DEV / RAM / CPU` strip in `ui.header` is on the
roadmap as a v0.2+ stretch — *not* a v0.1 deliverable — and only as a
composition of decoupled artifacts. Three rules:

1. **Probes are library code**; they return numbers and write to an
   `ObservableDict` bus.
2. **The bar is a thin element** that subscribes to bus keys; it doesn't own
   the probes.
3. **Both halves are independently usable.** A consumer can take the
   probes without the bar (Prometheus exporter, structlog interval) or the
   bar without the probes (drive it from their own bus).

The reasons: a kiosk maintainer's threat model isn't the same as a SaaS
operator's, and infra metrics visible to end-users is a security mistake
that an opinionated all-in-one widget can't avoid. Keeping the two halves
decoupled lets each consumer pick a different security/perf/UX trade-off.

## What we deliberately don't carry forward

- The full psutil server-side sampler — `psutil` is a heavy optional dep;
  the `resource.getrusage` + `/proc/self/status` path from PR #5867 covers
  the same ground without the dep.
- App-specific telemetry (PDF backup status probes, queue scheduler hooks,
  identity-dict wiring) — that's application UX leakage we drop on the way
  to a clean library extract.
