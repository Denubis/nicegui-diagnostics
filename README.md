# nicegui-diagnostics

> Runtime diagnostics endpoint and `ui.diagnostics_view()` element for [NiceGUI](https://nicegui.io) applications — a downstream standalone PyPI port of upstream draft [zauberzeug/nicegui#5867](https://github.com/zauberzeug/nicegui/pull/5867), plus five production-validated gap fills harvested from [MQFacultyOfArts/PromptGrimoireTool](https://github.com/MQFacultyOfArts/PromptGrimoireTool).

**Status:** pre-alpha. No code shipped yet. See the [project board](https://github.com/orgs/evnchn-nicegui/projects/1) for current scope and progress.

This repository exists so that the diagnostics work, currently blocked on an unresolved scope question in the upstream PR (core vs. extension package, see [discussion #5660](https://github.com/zauberzeug/nicegui/discussions/5660)), can ship independently on PyPI. If upstream decides to absorb the machinery later, this repo serves as the canonical reference; if not, it stays available to downstream consumers like PromptGrimoireTool.

## Why this exists

NiceGUI today has no runtime-introspection surface. When something leaks (asyncio task, websocket, RSS), the only options are ad-hoc `print()` debugging in your own code or reading framework source to know what's normal. Concretely, this lack of visibility has cost real time:

| Bug                                            | Bug found by                                                | Status                          |
| ---------------------------------------------- | ----------------------------------------------------------- | ------------------------------- |
| [#5803] page.py `Event.wait` leak              | per-qualname task grouping (now in #5867)                   | merged in NiceGUI 3.8 ([#5806]) |
| [#5804] Outbox `stop()` doesn't wake the loop  | named-task lookup + signal→`done()` latency (not in #5867)  | merged in NiceGUI 3.8 ([#5805]) |
| [#5930] `ui.timer` not cancelled mid-await     | `len(background_tasks)` vs `len(Client.instances)` delta    | merged in NiceGUI 3.10 ([#5931]) |
| 4.3 GB RSS OOM at PromptGrimoireTool (issue 434) | dual-source memory probe + 13h22m of snapshot trend data    | mitigated; hunt ongoing         |

[#5803]: https://github.com/zauberzeug/nicegui/issues/5803
[#5804]: https://github.com/zauberzeug/nicegui/issues/5804
[#5805]: https://github.com/zauberzeug/nicegui/pull/5805
[#5806]: https://github.com/zauberzeug/nicegui/pull/5806
[#5930]: https://github.com/zauberzeug/nicegui/issues/5930
[#5931]: https://github.com/zauberzeug/nicegui/pull/5931

## Scope (planned v0.1)

The package is intentionally a strict superset of upstream PR #5867 — the same opt-in `diagnostics=True` flag, the same `/_nicegui/diagnostics` endpoint, the same `ui.diagnostics_view()` element — plus the five "spec gaps" that PromptGrimoireTool's [internal gaps document](reference/promptgrimoire/2026-02-20-diagnostics-spec-gaps.md) found load-bearing in real incident response.

**Ported from PR #5867:**
- Opt-in `install()` (matches upstream `diagnostics=True`)
- `/_nicegui/diagnostics` JSON endpoint
- `ui.diagnostics_view()` element
- Task summary, memory metrics, per-client detail, server config
- Cross-platform memory probe (`resource.getrusage` + `/proc/self/status`)
- Pytest forwarding kwargs to `user_simulation`

**Architectural principle — measurement and display are decoupled.** Every
visible probe ships as a *measurement primitive* (pure Python, writes to an
`ObservableDict` metric bus) and a *display element* (subscribes to a bus).
Either half is usable without the other, so a Prometheus exporter can take
the probes without the UI, a kiosk can take the UI bound to its own bus,
and admin-only deployments can gate the display layer without rewriting the
probes. See `docs/design/00-vision.md`.

**New (the 5 gaps, priority-ordered per [PromptGrimoireTool spec-gaps doc](reference/promptgrimoire/2026-02-20-diagnostics-spec-gaps.md)):**
1. **Thread-stack dump on a separate-thread HTTP server** — captures stacks when the event loop is blocked. The async handler in PR #5867 hangs in that case.
2. **Task age (`oldest_age_s`) per qualname group** — counts alone are insufficient; a 142s-old `Event.wait` is unmistakably a leak.
3. **Client lifecycle counters** — `connects_total`, `disconnects_total`, `reconnects_total`, `deletes_total`. The `on_disconnect`-vs-`on_delete` semantic surprise needs counter evidence.
4. **Delta mode (`?delta=true`)** — accumulation is invisible without comparison; framework-side memory eliminates "remember previous snapshot" boilerplate.
5. **engine.io session count alongside NiceGUI client count** — discrepancy flags orphan sockets.

**Plus, addressing the 4 unresolved review comments from upstream PR #5867:**

| #   | File / area                              | Review point                                                                                                                    |
| --- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `testing/user_simulation.py`             | Mirror `screen.ui_run_kwargs` API for `user` fixture forwarding (currently `**run_kwargs` mismatch)                             |
| 2   | `elements/diagnostics_view.py`           | Should be composable `ui.diagnostics.XXXX()` sub-elements rather than a single log-dump                                          |
| 3   | `website/.../diagnostics_view_documentation.py` | `client_id` is a NiceGUI client-side secret; global-scope endpoint must be behind admin auth                                    |
| 4   | `nicegui/diagnostics.py:140`             | Endpoint registered post-`ui.run()` so misses `openapi.json` — bad for LLM/tool discovery. Needs pydantic response model + earlier registration |

## Relationship to upstream

- Upstream PR [#5867](https://github.com/zauberzeug/nicegui/pull/5867) is **draft, phase 1**, with `CONFLICTING` mergeable status since late March 2026 and no maintainer decision on the core-vs-extension question.
- This package targets a vendored, packageable port. It pins `nicegui>=3.10.0` so it can ride with NiceGUI releases for security/CVE fixes ([GHSA-w8wv-vfpc-hw2w](https://github.com/zauberzeug/nicegui/security/advisories/GHSA-w8wv-vfpc-hw2w), `#5931` timer leak) rather than chase a downstream branch.
- If/when the maintainer absorbs the work into core, this package becomes a thin shim that re-exports from `nicegui.diagnostics`.

## Repository layout

```
nicegui-diagnostics/
├── README.md, LICENSE, pyproject.toml
├── src/nicegui_diagnostics/        # the package itself (skeleton)
├── tests/                          # pytest using the NiceGUI User fixture
├── docs/design/                    # design synthesis from upstream + PG + private prior art
│   ├── 00-vision.md
│   ├── 01-maintainer-constraints-5660.md
│   ├── 02-api-surface.md
│   ├── 03-spec-gaps.md
│   ├── 04-leak-pr-provenance.md
│   ├── 05-private-prior-art.md
│   └── 06-promptgrimoire-context.md
└── reference/                      # vendored MIT-licensed source material
    ├── upstream-pr-5867/           # Denubis's draft, as of 0473e43
    ├── promptgrimoire/             # PG's vendored diagnostics + docs
    └── private-prior-art/          # citation-only technique notes (no code)
```

## Project board

Work is tracked on [evnchn-nicegui Project #1: nicegui-diagnostics v0.1](https://github.com/orgs/evnchn-nicegui/projects/1). Items are draft cards (not GitHub issues) to keep the upstream issue tracker quiet.

## Contributing

This is an investigatory repo. PRs welcome, but expect the API surface to change until v0.1 lands.

## Acknowledgements

- [@Denubis](https://github.com/Denubis) (Brian Ballsun-Stanton) — original PR #5867 author and the PromptGrimoireTool maintainer who fielded the 5 spec gaps from real incidents.
- [@falkoschindler](https://github.com/falkoschindler) and the [Zauberzeug](https://github.com/zauberzeug) team — for NiceGUI, and for the maintainer constraints in [#5660](https://github.com/zauberzeug/nicegui/discussions/5660) that shaped the design.
