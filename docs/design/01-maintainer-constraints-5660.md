# 01 — Maintainer constraints from #5660

Synthesized from the [origin discussion zauberzeug/nicegui#5660](https://github.com/zauberzeug/nicegui/discussions/5660),
[PR #5867](https://github.com/zauberzeug/nicegui/pull/5867) thread, and the
March 2026 review round.

## TL;DR

@falkoschindler has **not** ruled on core-vs-extension scope, despite the PR
author asking explicitly. The package is therefore a hedge: if upstream
absorbs the work, the package becomes a shim; if upstream stays silent, the
package is the home.

But Falko *has* expressed shape preferences that any design — in-core or
out-of-tree — must respect.

## Explicit "we WANT" from Falko

- **Opt-in via `diagnostics=True`** — and *truly* opt-in: when disabled, the
  endpoint must not be registered, the module must not be imported, no
  background tasks must run. PR #5867's current draft satisfies this with a
  feature flag on `AppConfig` checked before the import in `nicegui.py`.
- **Graphical, meaningful, actionable output** — *not* just a raw JSON dump.
  This is the reason `ui.diagnostics_view()` exists at all. (However, the
  v1 view in PR #5867 is a Log element; @evnchn's review point #2 argues
  composable sub-elements would be more in line with this constraint.)
- **Multi-axis instrumentation** — Falko was explicit that latency, event
  loop time, binding time, DOM/vDOM counts, and connected-client count are
  all things he wants to see. PR #5867 covers the first three plus client
  count; DOM/vDOM count is out of scope (browser-side, not server-side).
- **JS-side latency polling** — Falko rejected an engineio-modifying
  latency hack (the `poc-latency-measurement` branch) in favor of a JS poll
  from the client. This aligns with the `ui.run_javascript("1+1")` RTT
  pattern documented in
  [`docs/design/05-private-prior-art.md`](05-private-prior-art.md).

## Explicit "we will NOT" from Falko

- **PySnooper line tracing** — "too much" for core.
- **py-spy flamegraphs** — "too much" for core. (Both are bring-your-own-tool
  decisions, not anti-tool stances; the package can document them in
  recipes without bundling them.)
- **engineio-modifying probes** — see the rejected `poc-latency-measurement`
  branch in #5660.

## Explicit "we WANT" from @evnchn (review-round, blocking)

These are the four unresolved review-line comments on PR #5867 at HEAD
`0473e43`. Per `/tmp/agent_upstream_code.md`, none are marked resolved.

1. **`testing/user_simulation.py:20`** — mirror `screen.ui_run_kwargs` API on
   the `user` fixture for consistency. Currently `user_simulation(**run_kwargs)`
   is a one-shot kwargs splat with no equivalent on the pytest `user` fixture.
2. **`elements/diagnostics_view.py:1`** — should be composable
   `ui.diagnostics.task_summary()`, `ui.diagnostics.memory()`,
   `ui.diagnostics.client_detail()` sub-elements, not one Log-dump element.
3. **`website/.../diagnostics_view_documentation.py:40`** — `client_id` is a
   NiceGUI client-side secret (it backs storage and identity); a global-scope
   endpoint MUST require admin auth. Default-deny remote.
4. **`nicegui/diagnostics.py:140`** — endpoint registered post-`ui.run()` so
   it never lands in `openapi.json`. Bad for LLM-driven tool discovery and
   bad for API doc generation. Needs a pydantic response model and
   registration before app freeze.

## Inferred constraints (not stated, but consistent across maintainer behavior)

- **Don't pin a specific NiceGUI version.** Falko ships security patches and
  feature releases on a steady cadence; a downstream that pins (the way
  PromptGrimoireTool *had* to with the Denubis branch) is forced to choose
  between rebases and CVEs. The package therefore declares `nicegui>=3.10.0`
  as a *floor* and tracks the next major release range.
- **Don't ship breaking changes via patch versions of NiceGUI itself.**
  PR #5867 carefully avoids touching public API of existing modules. The
  package mirrors this: no monkey-patching of `nicegui.*` modules on import.
- **Composable extension is required.** Both Falko (multi-axis) and Denubis
  (app-specific fields like `app_ws_registry`) argue for subclass or
  registration hooks. The package's `extra_collectors: list[Callable]` API
  is the smallest thing that satisfies both.

## What this means for the package

Every design decision in `docs/design/02-api-surface.md` and downstream is
graded against this checklist:

- [ ] Module not imported if not installed
- [ ] Endpoint not registered if not installed
- [ ] Feature list is a list, not a bool
- [ ] Global scope requires `auth=` callable; client_id is treated as secret
- [ ] HTTP shape AND structlog shape both available, neither mandatory
- [ ] Stack dump works when the loop is blocked (separate thread)
- [ ] `extra_collectors` available for downstream extension
- [ ] `nicegui>=3.10.0` floor, no upper pin
- [ ] No monkey-patching of `nicegui.*` modules
- [ ] All four evnchn review points resolved
