# Upstream PR #5867 — verbatim snapshot

Files in this directory are MIT-licensed source from
[zauberzeug/nicegui#5867](https://github.com/zauberzeug/nicegui/pull/5867) by
[@Denubis](https://github.com/Denubis), pinned to commit
`0473e43118c30202a0ea2ef8de1e394e8245d4fe` (2026-03-11).

## Files

| File                                  | Upstream path                                                          | Lines |
| ------------------------------------- | ---------------------------------------------------------------------- | ----- |
| `diagnostics.py`                      | `nicegui/diagnostics.py`                                               | 141   |
| `diagnostics_view.py`                 | `nicegui/elements/diagnostics_view.py`                                 | 60    |
| `test_diagnostics.py`                 | `tests/test_diagnostics.py`                                            | 226   |
| `diagnostics_view_documentation.py`   | `website/documentation/content/diagnostics_view_documentation.py`      | 63    |

## Why pinned to that commit

This is the head of branch `diagnostics-5660` at the time PR #5867 was opened.
The PR has `CONFLICTING` mergeable status against `main` since late March 2026
(merge-conflict surface is documented in `docs/design/02-api-surface.md`).

## What is intentionally NOT vendored

Modified-file hunks for `app_config.py`, `nicegui.py`, `ui.py`, `ui_run.py`,
`testing/general.py`, `testing/user_simulation.py`, and the two `.py` test/doc
files. They're tiny patches against framework files that don't translate to a
standalone-package layout. The behavior they wire up is captured in our
[`docs/design/02-api-surface.md`](../../docs/design/02-api-surface.md).

## Re-fetch command

```bash
gh api -H "Accept: application/vnd.github.raw" \
  "repos/zauberzeug/nicegui/contents/nicegui/diagnostics.py?ref=0473e43118c30202a0ea2ef8de1e394e8245d4fe"
```
