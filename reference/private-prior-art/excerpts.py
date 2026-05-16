"""Pattern excerpts from one of evnchn's private NiceGUI applications.

Sanitized and generalized from production code that ran for ~5 months before
being removed in a production-stability pass. Reproduced here with permission
under MIT.

These excerpts are reference material for the design of `nicegui-diagnostics`
— not the package's production code itself. They illustrate three techniques
that complement upstream PR #5867:

1. ``measure_ws_rtt_ms`` — WebSocket round-trip latency via ``ui.run_javascript``
2. ``measure_js_burst_iterations`` — coarse client-side JS perf probe
3. ``ClientCountHeartbeat`` — heartbeat dict catching cases NiceGUI's own
   ``on_disconnect`` misses (browser tab killed, network cut, lid closed)

A short integration example at the bottom shows the ``ObservableDict`` /
``bind_text_from`` pattern that wires probes to in-page HUD labels without
any custom JS, SSE, or shared-state primitive.

Copyright (c) 2025-2026 evnchn -- MIT, see top-level LICENSE.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from nicegui import app, ui
from nicegui.observables import ObservableDict


# --- 1. WebSocket round-trip latency probe ------------------------------------

async def measure_ws_rtt_ms(timeout: float = 5.0) -> float:
    """Measure round-trip time of a no-op ``ui.run_javascript`` call.

    Sees network + serialization + browser RAF time on top of the server-side
    event-loop wait, complementing upstream PR #5867's
    ``measure_event_loop_lag`` (which sees only loop wait).

    Returns RTT in milliseconds. Saturate at 9999 for HUD rendering:
        ``rtt_ms = min(round(await measure_ws_rtt_ms()), 9999)``
    Suggested colour bands: green <100 ms, yellow <500 ms, red ≥500 ms.
    """
    t0 = datetime.now()
    await ui.run_javascript('1+1', timeout=timeout)
    return (datetime.now() - t0).total_seconds() * 1000.0


# --- 2. Client-side JS perf burst probe ---------------------------------------

_JS_BURST_SOURCE = """
const data = [...Array(1000).keys()];
const target = 800;
const duration = 10;  // milliseconds
const now = () => (performance && performance.now) ? performance.now() : Date.now();
let iterations = 0;
const t0 = now();
while (now() - t0 < duration) {
    if (data.includes(target)) iterations++;
}
iterations;
"""


async def measure_js_burst_iterations(timeout: float = 5.0) -> int:
    """Count how many ``[...].includes(target)`` calls finish in 10 ms client-side.

    Coarse but useful signal: a struggling client (background tab, throttled
    mobile, busy CPU) returns 10x-100x fewer iterations than a healthy one.
    Field-typical range observed: 1000 (struggling) ... 50000+ (healthy).

    Saturate at ``min(round(iterations / 10), 9999)`` for a 4-digit HUD column.
    """
    return int(await ui.run_javascript(_JS_BURST_SOURCE, timeout=timeout))


# --- 3. Client-count heartbeat (catches what on_disconnect misses) ------------

class ClientCountHeartbeat:
    """Track active clients by per-client heartbeat with TTL purge.

    NiceGUI's ``app.on_disconnect`` does not always fire (browser tab killed,
    network cut, laptop lid closed). A heartbeat dict + TTL purge keeps the
    count accurate without relying on the disconnect event alone.

    Usage::

        bus = ObservableDict()  # see make_metric_bus()
        heartbeat = ClientCountHeartbeat(bus, ttl_seconds=10)
        heartbeat.install()
        # in each page's header, after the page is built:
        heartbeat.report_alive_for(ui.context.client.id)
        ui.timer(5.0, lambda: heartbeat.report_alive_for(ui.context.client.id))

    The bus key ``"client_count"`` updates in place; any
    ``ui.label().bind_text_from(bus, "client_count", ...)`` reacts.
    """

    def __init__(self, bus: ObservableDict, ttl_seconds: float = 10.0) -> None:
        self.bus = bus
        self.ttl_seconds = ttl_seconds
        self._last_alive: dict[str, float] = {}

    def install(self) -> None:
        """Register ``app.on_connect`` / ``app.on_disconnect`` and seed bus key."""
        self.bus.setdefault('client_count', 0)
        app.on_connect(self._on_connect)
        app.on_disconnect(self._on_disconnect)

    def report_alive_for(self, client_id: str) -> None:
        """Call from each page on a timer (e.g. every 5 s)."""
        self._last_alive[client_id] = datetime.now().timestamp()
        self._recount()

    def _on_connect(self, client: Any) -> None:
        self._last_alive[client.id] = datetime.now().timestamp()
        self._recount()

    def _on_disconnect(self, client: Any) -> None:
        self._last_alive.pop(client.id, None)
        self._recount()

    def _recount(self) -> None:
        now = datetime.now().timestamp()
        live = {
            cid: ts for cid, ts in self._last_alive.items()
            if now - ts < self.ttl_seconds
        }
        self._last_alive = live
        self.bus['client_count'] = len(live)


# --- 4. ObservableDict as a reactive metric bus -------------------------------

def make_metric_bus() -> ObservableDict:
    """Return a fresh ``ObservableDict`` for use as a reactive metric bus.

    Probes write keys::

        bus = make_metric_bus()
        bus['cpu_percent'] = 42
        bus['client_count'] = 7

    Any HUD label binds them::

        ui.label().bind_text_from(
            bus, 'cpu_percent',
            backward=lambda x: f'CPU:{min(round(x), 99):02d}%',
        )

    No custom JS, no SSE, no shared-state primitive — NiceGUI's
    ``ObservableDict`` + ``bind_text_from`` already handles change
    propagation.
    """
    return ObservableDict()


# --- 5. Example wiring (read-only example, not exported) ----------------------

def _example_hud_header(bus: ObservableDict) -> None:
    """Reference implementation of an opacity-50 HUD strip in ``ui.header``.

    Three probes wired to three labels via bus binding. The HUD is mounted
    once per page; the probes can be driven by a per-client ``ui.timer`` or
    a shared background task.
    """
    with ui.header(fixed=False).classes('bg-transparent p-0 gap-1 justify-between '
                                        'no-wrap font-mono opacity-50'):
        lag_lbl = ui.label('LAG:???')
        spd_lbl = ui.label('SPD:???')
        cli_lbl = ui.label('DEV:???')

        cli_lbl.bind_text_from(
            bus, 'client_count',
            backward=lambda x: f'DEV:{min(round(x), 999):03d}',
        )

    async def tick() -> None:
        rtt = await measure_ws_rtt_ms()
        rtt_ms = min(round(rtt), 9999)
        lag_lbl.set_text(f'LAG{rtt_ms:04d}' if rtt_ms >= 1000 else f'LAG:{rtt_ms:03d}')

        burst = await measure_js_burst_iterations()
        spd_k = min(round(burst / 10), 9999)
        spd_lbl.set_text(f'SPD{spd_k:04d}' if spd_k >= 1000 else f'SPD:{spd_k:03d}')

    ui.timer(5.0, tick)
