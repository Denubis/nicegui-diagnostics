# 05 — Private prior-art techniques

Summary of the three techniques drawn from one of @evnchn's private
NiceGUI applications (vendored under MIT into
[`reference/private-prior-art/excerpts.py`](../../reference/private-prior-art/excerpts.py))
and how they map onto this package's design.

The source application carried these in production for ~5 months in 2025,
then removed them during a stability pass — a "we don't need this in prod"
decision, not a "this is buggy" decision. Working code, conservatively
sized, with field experience behind every shape choice.

## Technique 1 — WebSocket round-trip latency probe

`measure_ws_rtt_ms()` — schedules `ui.run_javascript("1+1", timeout=5)` and
measures the round-trip with `datetime.now()` deltas.

**What it sees that the upstream `measure_event_loop_lag` doesn't:** network
RTT, browser RAF / event-loop time, JSON serialization. The server-side
probe sees only loop wait; together they bracket the user-visible latency.

**Maps to package design:**
- `probes/ws_rtt.py` provides the measurement primitive.
- `elements/ws_rtt.py` provides the optional display element.
- Feature flag `"js_rtt"`.

**Cost:** ~one round-trip's worth of bandwidth, scheduled per-client per-tick.
At a 5 s tick that's ~12 calls/min/client. Cheap by absolute terms; the
consumer can opt out via feature flag.

**Field calibration:** the 4-digit (`LAG NNNN ms`) format was added in
production because real users were *regularly* hitting the saturated band.
The format choice is field-tuned, not theoretical.

## Technique 2 — Client-count heartbeat dict

`ClientCountHeartbeat` — registers `app.on_connect` + `app.on_disconnect`
and maintains a `last_alive: dict[str, float]` keyed by client_id, with a
TTL purge driven by the same `ui.timer` cadence as the latency probe.

**What it sees that PR #5867's `clients_connected` doesn't:** tab-killed,
network-cut, lid-closed clients. NiceGUI's own `on_disconnect` doesn't
always fire in those cases; the heartbeat catches it on the next purge.

**Maps to package design:**
- `probes/heartbeat.py` provides the heartbeat dict + purge logic.
- It's a primary contributor to `lifecycle.deletes_total` (gap 3).
- Feature flag `"heartbeat"`.

**Subtle invariant:** the heartbeat MUST be reported from each page's own
context (`ui.context.client.id`), not from a background task. If the
background task tries to enumerate `Client.instances`, it sees clients
whose page has already navigated away — which is exactly the staleness the
heartbeat was added to detect.

## Technique 3 — `ObservableDict` as reactive metric bus

`make_metric_bus()` — returns a fresh `ObservableDict`. Probes write keys
(`bus['cpu_percent'] = 42`); display elements bind to them
(`ui.label().bind_text_from(bus, 'cpu_percent', backward=...)`).

**What it gives that ad-hoc state doesn't:** no custom JS, no SSE, no Redis
pub/sub, no shared-state primitive. NiceGUI's `ObservableDict` already
fires change-propagation on `__setitem__`; `bind_text_from` already
subscribes. Five lines of glue, no new infrastructure.

**Maps to package design:**
- Internal singleton `_bus.py` for the package's own probes.
- Public helper `make_metric_bus()` so consumers can run their own buses
  for separation (e.g. one bus per admin scope, one per kiosk scope).
- This is the substrate that makes the
  [decoupling principle in 00-vision.md](00-vision.md#decoupling-measurement-from-display)
  cheap.

## Why this complements PR #5867 instead of competing with it

PR #5867 is a server-side snapshot — one JSON document, one collection
function, no JS. These three techniques are client-side and live-binding —
they need NiceGUI's UI substrate to be cheap.

Both halves are needed because:
- Server-only diagnostics can't see WebSocket RTT (no client-side timing).
- Server-only `on_disconnect` doesn't catch tab-kill / network-cut.
- One JSON snapshot can't drive a live HUD; binding can.

The package therefore ships both, decoupled, behind feature flags.

## Stretch goal: "Web Speed Debug Bar" v0.2+

Once the three techniques and PR #5867's snapshot are both running, the
opacity-50 HUD strip becomes a thin composition:

```python
with ui.diagnostics.web_speed_bar(scope="admin"):
    ui.diagnostics.ws_rtt()           # LAG:NNN
    ui.diagnostics.js_burst()         # SPD:NNN
    ui.diagnostics.client_count()     # DEV:NNN
    ui.diagnostics.memory_rss()       # RAM:NN%
```

Each sub-element is independently usable. The bar is the composition, not
a monolith. Reasons for decoupling are recorded in
[`00-vision.md`](00-vision.md#decoupling-measurement-from-display).
