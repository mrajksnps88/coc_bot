"""Windows direct-input automation backend.

Provides a :class:`WindowsInput` implementation of :class:`InputInterface`
that drives mouse / keyboard events through the ``pydirectinput`` library.
This is a **fallback** for non-ADB environments and is **Windows-only**.

Note
----
``pydirectinput`` must be installed separately (``pip install pydirectinput``).
An :class:`ImportError` is raised with a clear message if the library is
unavailable at instantiation time.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from coc_bot.modules.input.base import InputInterface

if TYPE_CHECKING:
    import pydirectinput as _pdi_type  # for type stubs only

logger: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import helper
# ---------------------------------------------------------------------------

_pdi: _pdi_type | None = None  # type: ignore[name-defined]


def _get_pdi() -> _pdi_type:  # type: ignore[name-defined]
    """Lazily import ``pydirectinput``, raising a clear error if missing.

    Returns
    -------
    module
        The ``pydirectinput`` module.

    Raises
    ------
    ImportError
        If ``pydirectinput`` is not installed.
    """
    global _pdi  # noqa: PLW0603
    if _pdi is None:
        try:
            import pydirectinput  # type: ignore[import-untyped]

            _pdi = pydirectinput
        except ImportError as exc:
            raise ImportError(
                "pydirectinput is required for WindowsInput but is not "
                "installed.  Install it with:  pip install pydirectinput\n"
                "Note: pydirectinput is Windows-only."
            ) from exc
    return _pdi  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SWIPE_STEP_INTERVAL_S: float = 0.016  # ≈ 60 fps
_TYPEWRITE_INTERVAL_S: float = 0.05


class WindowsInput(InputInterface):
    """Input backend using ``pydirectinput`` for Windows environments.

    This is a **fallback** for scenarios where ADB is not available.
    It translates all pixel coordinates by ``(offset_x, offset_y)`` so the
    caller can work with game-relative coordinates even when the game
    window is not at ``(0, 0)``.

    Parameters
    ----------
    offset_x:
        Horizontal pixel offset added to all coordinates (default ``0``).
    offset_y:
        Vertical pixel offset added to all coordinates (default ``0``).
    dry_run:
        If ``True``, actions are logged but **not** executed.

    Raises
    ------
    ImportError
        If ``pydirectinput`` is not installed.
    """

    def __init__(
        self,
        offset_x: int = 0,
        offset_y: int = 0,
        dry_run: bool = False,
    ) -> None:
        self._offset_x: int = offset_x
        self._offset_y: int = offset_y
        self._dry_run: bool = dry_run

        # Eagerly validate that pydirectinput is available.
        if not dry_run:
            _get_pdi()

    # ------------------------------------------------------------------
    # Coordinate translation
    # ------------------------------------------------------------------

    def _translate(self, x: int, y: int) -> tuple[int, int]:
        """Translate game coordinates to screen coordinates.

        Parameters
        ----------
        x:
            Game-relative horizontal coordinate.
        y:
            Game-relative vertical coordinate.

        Returns
        -------
        tuple[int, int]
            ``(screen_x, screen_y)`` after applying the configured offset.
        """
        return x + self._offset_x, y + self._offset_y

    # ------------------------------------------------------------------
    # Public API (InputInterface)
    # ------------------------------------------------------------------

    def tap(self, x: int, y: int) -> None:
        """Click at ``(x, y)`` (offset-translated).

        Parameters
        ----------
        x:
            Game-relative horizontal coordinate.
        y:
            Game-relative vertical coordinate.
        """
        sx, sy = self._translate(x, y)
        logger.debug("tap(%d, %d) → screen (%d, %d)", x, y, sx, sy)
        if self._dry_run:
            logger.debug("[DRY-RUN] Would click at (%d, %d)", sx, sy)
            return
        pdi = _get_pdi()
        pdi.click(sx, sy)

    def multi_tap(self, points: list[tuple[int, int]]) -> None:
        """Tap multiple points in rapid succession."""
        if self._dry_run:
            logger.debug("[DRY-RUN] Would multi-tap %d points", len(points))
            return
        pdi = _get_pdi()
        for (x, y) in points:
            sx, sy = self._translate(x, y)
            pdi.click(sx, sy)
            time.sleep(0.05)

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
        hold_before_swipe_ms: int = 0,
    ) -> None:
        """Simulate a swipe gesture from ``(x1, y1)`` to ``(x2, y2)``.

        The pointer moves in small linear steps over *duration_ms*
        milliseconds with the left mouse button held down.

        Parameters
        ----------
        x1, y1:
            Start coordinates (game-relative).
        x2, y2:
            End coordinates (game-relative).
        duration_ms:
            Total duration of the swipe in milliseconds.
        hold_before_swipe_ms:
            Time to hold down the mouse at the start coordinate before moving.
        """
        sx1, sy1 = self._translate(x1, y1)
        sx2, sy2 = self._translate(x2, y2)
        logger.debug(
            "swipe(%d, %d) → (%d, %d) over %d ms  [screen (%d,%d)→(%d,%d)]",
            x1, y1, x2, y2, duration_ms, sx1, sy1, sx2, sy2,
        )
        if self._dry_run:
            logger.debug(
                "[DRY-RUN] Would swipe from (%d, %d) to (%d, %d)",
                sx1, sy1, sx2, sy2,
            )
            return

        pdi = _get_pdi()
        duration_s: float = duration_ms / 1000.0
        steps: int = max(1, int(duration_s / _SWIPE_STEP_INTERVAL_S))
        dx: float = (sx2 - sx1) / steps
        dy: float = (sy2 - sy1) / steps

        pdi.moveTo(sx1, sy1)
        pdi.mouseDown()
        try:
            if hold_before_swipe_ms > 0:
                time.sleep(hold_before_swipe_ms / 1000.0)
                
            for i in range(1, steps + 1):
                cx: int = int(sx1 + dx * i)
                cy: int = int(sy1 + dy * i)
                pdi.moveTo(cx, cy)
                time.sleep(_SWIPE_STEP_INTERVAL_S)
        finally:
            pdi.mouseUp()

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        """Long-press at ``(x, y)`` for *duration_ms* milliseconds.

        Moves to the target position, holds the left mouse button down
        for the specified duration, then releases.

        Parameters
        ----------
        x:
            Game-relative horizontal coordinate.
        y:
            Game-relative vertical coordinate.
        duration_ms:
            Hold duration in milliseconds.
        """
        sx, sy = self._translate(x, y)
        logger.debug(
            "long_press(%d, %d) for %d ms  [screen (%d, %d)]",
            x, y, duration_ms, sx, sy,
        )
        if self._dry_run:
            logger.debug(
                "[DRY-RUN] Would long-press at (%d, %d) for %d ms",
                sx, sy, duration_ms,
            )
            return

        pdi = _get_pdi()
        pdi.moveTo(sx, sy)
        pdi.mouseDown()
        time.sleep(duration_ms / 1000.0)
        pdi.mouseUp()

    def text(self, content: str) -> None:
        """Type *content* character-by-character via ``pydirectinput``.

        Parameters
        ----------
        content:
            The string to type.  Each character is sent with a short
            inter-key interval (``0.05 s``).
        """
        logger.debug("text(%r)", content)
        if self._dry_run:
            logger.debug("[DRY-RUN] Would type: %r", content)
            return
        pdi = _get_pdi()
        pdi.typewrite(content, interval=_TYPEWRITE_INTERVAL_S)
