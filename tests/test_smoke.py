"""Smoke tests — verify the package can be imported and has expected metadata."""
from __future__ import annotations


def test_import() -> None:
    import nicegui_diagnostics

    assert nicegui_diagnostics.__version__ == "0.0.0"


def test_zero_side_effects_on_import() -> None:
    """Importing the package must not register routes, start tasks, or touch NiceGUI state.

    This is the [#5660 maintainer constraint](
    https://github.com/zauberzeug/nicegui/discussions/5660): truly opt-in means
    that simply importing the module is free. Once ``install()`` exists, this
    test will be extended to assert no routes have been added to ``app``.
    """
    import sys

    sys.modules.pop("nicegui_diagnostics", None)
    sys.modules.pop("nicegui_diagnostics.elements", None)

    import nicegui_diagnostics  # noqa: F401 -- import is the test

    # Subpackage should NOT be auto-imported (lazy-import discipline)
    assert "nicegui_diagnostics.elements" not in sys.modules
