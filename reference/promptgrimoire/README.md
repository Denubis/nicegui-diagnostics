# PromptGrimoireTool — vendored reference

Files in this directory are MIT-licensed source from
[MQFacultyOfArts/PromptGrimoireTool](https://github.com/MQFacultyOfArts/PromptGrimoireTool),
the in-production NiceGUI application that authored the spec-gap list this
package implements.

Maintained by [@Denubis](https://github.com/Denubis) (Brian Ballsun-Stanton).

## Files

| File                                       | Upstream path                                          | Why it's here                                                                                  |
| ------------------------------------------ | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `diagnostics.py`                           | `src/promptgrimoire/diagnostics.py`                    | The full 363-line vendored copy of PR #5867's collection function, extended with app fields    |
| `admission.py`                             | `src/promptgrimoire/admission.py`                      | AIMD admission gate; consumes `event_loop_lag_ms` from snapshot. No NiceGUI imports.            |
| `dev_endpoints.py`                         | `src/promptgrimoire/dev_endpoints.py`                  | Chaos primitives. `/api/dev/block-loop` is gold for E2E AIMD testing.                          |
| `logging_config.py`                        | `src/promptgrimoire/logging_config.py`                 | TTY-aware structlog renderer; JSONRenderer for systemd journal. Pattern source for emitter.    |
| `sd_notify.py`                             | `src/promptgrimoire/sd_notify.py`                      | 39-LOC `AF_UNIX SOCK_DGRAM` to `$NOTIFY_SOCKET`. Zero deps.                                    |
| `2026-02-20-diagnostics-spec-gaps.md`      | `docs/design-plans/2026-02-20-diagnostics-spec-gaps.md` | The canonical 5-gap list with priority ordering and incident-phase justifications              |
| `2026-03-30-lag-admission-gate.md`         | `docs/design-plans/2026-03-30-lag-admission-gate.md`   | AIMD design with acceptance criteria + hysteresis values                                       |
| `lag-watchdog.sh`                          | `deploy/lag-watchdog.sh`                               | Out-of-process bash + `journalctl | jq` consumer with 3-rule restart logic                     |

## Why we vendor rather than depend on the project

PromptGrimoireTool is an application, not a library — installing it as a dep
would pull in pycrdt, Stytch auth, FastAPI extras, and 30+ other things this
package has no business depending on. The relevant modules are mostly
self-contained (see the [`/tmp/agent_pg_code.md`](../../docs/design/06-promptgrimoire-context.md)
NiceGUI-integration-surface section) and small enough to read.

## What is intentionally NOT vendored

`config.py`, `word_count.py`, `auth/`, `crdt/`, `db/` — application code that
isn't relevant to a diagnostics package. The `_flush_milkdown_to_crdt` /
`_persist_dirty_workspaces` calls in `diagnostics.py` will be left as-is in
this reference copy so the original ordering invariant is visible, but the
ported version in `src/nicegui_diagnostics/` will replace them with
`on_before_restart: list[Callable]` hooks.
