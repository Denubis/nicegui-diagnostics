# 04 — Diagnostic-field provenance: which leak proves which field

Every diagnostic field in this package's data model is justified by a
specific upstream NiceGUI bug that was found (or *would have been found
faster*) by emitting that field. This document is the authoritative
provenance map.

Synthesised from the agent digest at `/tmp/agent_leak_prs.md`.

## The bugs

| # | Issue / PR                            | Bug                                                                                                                    | Merged    |
| - | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | --------- |
| A | [#5803]/[#5806]                       | `page.py decorated()` doesn't cancel `task_wait_for_connection` when the page coroutine wins the FIRST_COMPLETED race  | 3.8       |
| B | [#5804]/[#5805]                       | `Outbox.stop()` flips `_should_stop` but doesn't wake the `Event.wait(timeout=1.0)` sleeping loop                       | 3.8       |
| C | [#5930]/[#5931]                       | `ui.timer` callbacks awaiting long ops aren't cancelled mid-execution when the client is deleted                       | 3.10      |
| D | [GHSA-w8wv-vfpc-hw2w]                 | `PurePosixPath(filename).name` doesn't strip `\\` on Windows → arbitrary file write (CVE-2026-39844)                    | 3.10      |
| E | PromptGrimoireTool issue 434          | 13h22m RSS climb to 4.3 GB SIGABRT; cause hypothesis: glibc arena fragmentation                                         | mitigated |

[#5803]: https://github.com/zauberzeug/nicegui/issues/5803
[#5804]: https://github.com/zauberzeug/nicegui/issues/5804
[#5805]: https://github.com/zauberzeug/nicegui/pull/5805
[#5806]: https://github.com/zauberzeug/nicegui/pull/5806
[#5930]: https://github.com/zauberzeug/nicegui/issues/5930
[#5931]: https://github.com/zauberzeug/nicegui/pull/5931
[GHSA-w8wv-vfpc-hw2w]: https://github.com/zauberzeug/nicegui/security/advisories/GHSA-w8wv-vfpc-hw2w

D (the security fix) is not diagnostic-discoverable — it was a code-review
find. It's listed here because it's the *reason* this package pins
`nicegui>=3.10.0`: a downstream that pins NiceGUI to ride with the Denubis
branch (instead of mainline) is forced to choose between rebases and CVEs.

## Provenance map: bug → field

| Bug | Diagnostic that found it / could find it                            | In PR #5867? | Package shipping plan                  |
| --- | ------------------------------------------------------------------- | ------------ | -------------------------------------- |
| A   | per-qualname task count                                             | yes          | port verbatim                          |
| A   | `task.get_name()` distinguishing leaked Event.wait                  | **no**       | add as `name` field on TaskGroup entries|
| B   | named-task substring match (`"outbox loop" in t.get_name()`)        | **no**       | as above                               |
| B   | signal→`done()` wall-clock latency                                  | **no**       | gap 2 `oldest_age_s` covers this        |
| C   | `len(background_tasks.running_tasks)`                               | yes          | port verbatim                          |
| C   | `len(Client.instances)`                                             | yes          | port verbatim                          |
| C   | **delta** of the above two across snapshots                         | **no**       | gap 4 `?delta=true`                    |
| E   | `current_rss_bytes` trend over hours                                | yes          | port verbatim                          |
| E   | `clients_total` vs `clients_connected` gap under load              | yes          | port verbatim                          |
| E   | per-coroutine task age (`oldest_age_s`)                             | **no**       | gap 2                                  |
| (general)| `connects_total` / `disconnects_total` / `reconnects_total` / `deletes_total` ratio | **no** | gap 3                       |
| (general)| `engineio_sessions` vs `nicegui_clients` discrepancy            | **no**       | gap 5                                  |
| (general)| out-of-loop stack capture (separate-thread HTTPServer)          | **no**       | gap 1                                  |
| (general)| structured-log interval emission for journald/jq                | **no**       | dedicated emitter sub-module           |

## Reading this table

Rows marked **no** in column 3 are the package's value-add over PR #5867
as it currently stands. Most originate from PG's spec-gaps list and a few
from the live debugging of bugs A/B that motivated PR #5867 itself.

The PR #5867 author and PromptGrimoireTool maintainer is the same person,
which is why the gap list is so well-aligned with the open PR. We are
building the consolidated v0.1 deliverable; this is the value-add over
what's currently in flight.

## Why pin `nicegui>=3.10.0`

Floor reasons:

- D ([GHSA-w8wv-vfpc-hw2w]) was patched in 3.10.0; we cannot ship a
  diagnostics package that recommends a vulnerable framework.
- C ([#5931]) was merged in 3.10; the timer-leak diagnostic example in this
  doc only fires correctly on 3.10+.

No ceiling reason. We track NiceGUI's API surface; if anything we depend
on moves, we follow.
