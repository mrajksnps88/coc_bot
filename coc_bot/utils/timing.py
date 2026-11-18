"""Timing and delay utilities.

Provides helpers for human-like random delays, screen-change detection via
polling, cooldown management, and Gaussian-noise delay humanization.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Callable

import numpy as np

from coc_bot.utils.image_utils import images_differ

logger: logging.Logger = logging.getLogger(__name__)


def random_delay(min_s: float, max_s: float) -> float:
    """Sleep for a uniformly random duration between *min_s* and *max_s*.

    Args:
        min_s: Minimum sleep duration in seconds.
        max_s: Maximum sleep duration in seconds.

    Returns:
        The actual duration slept (in seconds).

    Raises:
        ValueError: If *min_s* is greater than *max_s*.
    """
    if min_s > max_s:
        raise ValueError(
            f"min_s ({min_s}) must be <= max_s ({max_s})"
        )

    delay: float = random.uniform(min_s, max_s)
    logger.debug("Sleeping for %.3fs (range [%.3f, %.3f])", delay, min_s, max_s)
    time.sleep(delay)
    return delay


def wait_for_change(
    capture_fn: Callable[[], np.ndarray],
    timeout: float = 10.0,
    check_interval: float = 0.5,
) -> bool:
    """Poll the screen until it changes or *timeout* elapses.

    An initial frame is captured immediately.  Subsequent frames are compared
    against it using :func:`~coc_bot.utils.image_utils.images_differ`.

    Args:
        capture_fn: A callable that returns the current screen image as an
                    :class:`numpy.ndarray`.
        timeout: Maximum time to wait (seconds).
        check_interval: Time between successive captures (seconds).

    Returns:
        ``True`` if a change was detected within *timeout*, ``False`` otherwise.
    """
    initial_frame: np.ndarray = capture_fn()
    start: float = time.monotonic()

    logger.debug(
        "Waiting for screen change (timeout=%.1fs, interval=%.2fs)",
        timeout,
        check_interval,
    )

    while time.monotonic() - start < timeout:
        time.sleep(check_interval)
        current_frame: np.ndarray = capture_fn()
        if images_differ(initial_frame, current_frame):
            elapsed: float = time.monotonic() - start
            logger.debug("Screen change detected after %.2fs", elapsed)
            return True

    logger.debug("No screen change detected within %.1fs", timeout)
    return False


class Cooldown:
    """A simple cooldown timer.

    Args:
        duration: The cooldown duration in seconds.
    """

    def __init__(self, duration: float) -> None:
        self._duration: float = duration
        self._last_reset: float = 0.0  # Epoch 0 ⇒ immediately ready.

    def is_ready(self) -> bool:
        """Return ``True`` if the cooldown period has elapsed."""
        return time.monotonic() - self._last_reset >= self._duration

    def reset(self) -> None:
        """Reset the cooldown, starting a new waiting period."""
        self._last_reset = time.monotonic()

    def remaining(self) -> float:
        """Return the number of seconds until the cooldown is ready.

        Returns:
            Seconds remaining, or ``0.0`` if already ready.
        """
        left: float = self._duration - (time.monotonic() - self._last_reset)
        return max(0.0, left)

    def __repr__(self) -> str:
        return (
            f"Cooldown(duration={self._duration}, "
            f"remaining={self.remaining():.2f})"
        )


def humanize_delay(base_delay: float, sigma: float = 0.1) -> float:
    """Add Gaussian noise to *base_delay* for a more human-like timing.

    The result is clamped so it never drops below ``base_delay * 0.5``.

    Args:
        base_delay: The base delay in seconds.
        sigma: Standard deviation of the Gaussian noise as a fraction of
               *base_delay*.

    Returns:
        The jittered delay value (not slept – the caller decides when to use
        it).
    """
    noise: float = random.gauss(0, sigma * base_delay)
    jittered: float = base_delay + noise
    minimum: float = base_delay * 0.5
    clamped: float = max(minimum, jittered)
    logger.debug(
        "Humanized delay: base=%.3f, noise=%.3f, result=%.3f",
        base_delay,
        noise,
        clamped,
    )
    return clamped
