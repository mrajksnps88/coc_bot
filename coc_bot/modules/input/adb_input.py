"""ADB-backed input automation.

Sends touch / text events to an Android device or emulator via the
``input`` shell command over ADB.  A :class:`threading.Lock` guarantees
thread-safe command execution.  Tap coordinates receive small random
jitter (Gaussian, σ = 1.5 px, clamped to ±3 px) for human-like variance.
"""
from __future__ import annotations

import logging
import random
import threading
from typing import TYPE_CHECKING

from coc_bot.modules.input.base import InputInterface
from coc_bot.utils.timing import random_delay

if TYPE_CHECKING:
    from coc_bot.config.settings import TimingSettings
    from coc_bot.utils.adb import ADBConnection

logger: logging.Logger = logging.getLogger(__name__)

_JITTER_SIGMA: float = 1.5
_JITTER_MAX: int = 3


def _jitter(value: int) -> int:
    """Add Gaussian jitter to a pixel coordinate.

    Parameters
    ----------
    value:
        Original pixel coordinate.

    Returns
    -------
    int
        Coordinate shifted by a random offset drawn from
        ``N(0, _JITTER_SIGMA)`` and clamped to ``±_JITTER_MAX``.
    """
    offset: float = random.gauss(0, _JITTER_SIGMA)
    clamped: int = int(max(-_JITTER_MAX, min(_JITTER_MAX, round(offset))))
    return value + clamped


class ADBInput(InputInterface):
    """Input backend that dispatches touch events through ADB.

    Parameters
    ----------
    connection:
        Active :class:`ADBConnection` used to execute shell commands.
    timing:
        :class:`TimingSettings` controlling inter-action delays.
    dry_run:
        If ``True``, commands are logged but **not** sent to the device.
    """

    def __init__(
        self,
        connection: ADBConnection,
        timing: TimingSettings,
        dry_run: bool = False,
    ) -> None:
        self._connection: ADBConnection = connection
        self._timing: TimingSettings = timing
        self._dry_run: bool = dry_run
        self._lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute(self, cmd: str) -> None:
        """Execute an ADB shell command under the thread lock.

        Parameters
        ----------
        cmd:
            The full ``input …`` command string to run on the device.
        """
        with self._lock:
            if self._dry_run:
                logger.debug("[DRY-RUN] Would execute: %s", cmd)
                return
            self._connection.execute(cmd)

    # ------------------------------------------------------------------
    # Public API (InputInterface)
    # ------------------------------------------------------------------

    def tap(self, x: int, y: int) -> None:
        """Tap at ``(x, y)`` with small random jitter.

        A Gaussian offset (σ=1.5 px, clamped ±3 px) is applied to both
        axes before the event is dispatched.

        Parameters
        ----------
        x:
            Target horizontal pixel coordinate.
        y:
            Target vertical pixel coordinate.
        """
        jx: int = _jitter(x)
        jy: int = _jitter(y)
        logger.debug("tap(%d, %d) → jittered to (%d, %d)", x, y, jx, jy)
        self._execute(f"input tap {jx} {jy}")
        random_delay(*self._timing.action_delay_range)

    def multi_tap(self, points: list[tuple[int, int]]) -> None:
        """Tap multiple points in rapid succession."""
        for (x, y) in points:
            jx: int = _jitter(x)
            jy: int = _jitter(y)
            self._execute(f"input tap {jx} {jy}")
        random_delay(*self._timing.action_delay_range)

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
        hold_before_swipe_ms: int = 0,
    ) -> None:
        """Swipe from ``(x1, y1)`` to ``(x2, y2)`` over *duration_ms* ms.

        Parameters
        ----------
        x1, y1:
            Start coordinates.
        x2, y2:
            End coordinates.
        duration_ms:
            Duration of the swipe gesture in milliseconds.
        """
        logger.debug(
            "swipe(%d, %d) → (%d, %d) over %d ms",
            x1, y1, x2, y2, duration_ms,
        )
        self._execute(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        """Long-press at ``(x, y)`` for *duration_ms* milliseconds.

        Implemented as a zero-distance swipe (``input swipe x y x y ms``).

        Parameters
        ----------
        x:
            Horizontal pixel coordinate.
        y:
            Vertical pixel coordinate.
        duration_ms:
            Hold duration in milliseconds.
        """
        logger.debug("long_press(%d, %d) for %d ms", x, y, duration_ms)
        # Adding 1px offset to x2 and y2 prevents Android from filtering out zero-distance swipes
        self._execute(f"input swipe {x} {y} {x+1} {y+1} {duration_ms}")

    def text(self, content: str) -> None:
        """Type *content* into the currently focused input field via ADB.

        Parameters
        ----------
        content:
            Text string to type.  Spaces and special characters are
            handled by the ADB ``input text`` command.
        """
        logger.debug("text(%r)", content)
        self._execute(f"input text {content}")
