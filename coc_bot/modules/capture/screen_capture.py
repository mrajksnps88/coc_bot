"""Desktop screen capture backend using DXcam (with mss fallback)."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import numpy as np

from coc_bot.modules.capture.base import CaptureInterface

logger: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency availability flags
# ---------------------------------------------------------------------------
_HAS_DXCAM: bool = False
_HAS_MSS: bool = False

try:
    import dxcam  # type: ignore[import-untyped]

    _HAS_DXCAM = True
except ImportError:
    pass

try:
    import mss as _mss  # type: ignore[import-untyped]

    _HAS_MSS = True
except ImportError:
    pass


class ScreenCapture(CaptureInterface):
    """Desktop screen capture using **DXcam** with an **mss** fallback.

    DXcam provides zero-copy GPU-accelerated screen capture on Windows via
    the Desktop Duplication API.  When DXcam is unavailable (e.g. on older
    systems or non-Windows platforms) the backend transparently falls back
    to **mss**, a cross-platform screenshot library.

    Parameters:
        monitor_index: Zero-based index of the monitor to capture.
        region: Optional ``(left, top, right, bottom)`` sub-region to
            capture.  When *None* the entire monitor is captured.

    Raises:
        ImportError: If neither ``dxcam`` nor ``mss`` can be imported.
    """

    _MAX_GRAB_RETRIES: int = 5
    """Maximum number of retry attempts for a ``None`` frame from DXcam."""

    _GRAB_RETRY_DELAY: float = 0.05
    """Seconds to sleep between DXcam grab retries."""

    def __init__(
        self,
        monitor_index: int = 0,
        region: tuple[int, int, int, int] | None = None,
    ) -> None:
        if not _HAS_DXCAM and not _HAS_MSS:
            raise ImportError(
                "Neither 'dxcam' nor 'mss' is installed. "
                "Install at least one: pip install dxcam   OR   pip install mss",
            )

        self._monitor_index: int = monitor_index
        self._region: tuple[int, int, int, int] | None = region

        # Runtime handles — initialised in connect().
        self._camera: Any | None = None  # dxcam.DXCamera | None
        self._sct: Any | None = None  # mss.mss | None
        self._using_dxcam: bool = False
        self._resolution_cache: tuple[int, int] | None = None

    # ------------------------------------------------------------------
    # CaptureInterface implementation
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Create the underlying capture device.

        Attempts to initialise DXcam first.  If the import previously
        failed, falls back to mss and logs a warning.
        """
        if _HAS_DXCAM:
            try:
                self._camera = dxcam.create(device_idx=self._monitor_index, output_color="BGR")
                self._using_dxcam = True
                logger.info(
                    "DXcam capture initialised on monitor %d.", self._monitor_index,
                )
                return
            except Exception:
                logger.warning(
                    "DXcam initialisation failed; falling back to mss.",
                    exc_info=True,
                )

        if _HAS_MSS:
            self._sct = _mss.mss()
            self._using_dxcam = False
            logger.warning(
                "Using mss fallback for screen capture (monitor %d).",
                self._monitor_index,
            )
            return

        # Should be unreachable due to __init__ guard, but just in case.
        raise ImportError(
            "Neither 'dxcam' nor 'mss' is available for screen capture.",
        )

    def grab(self) -> np.ndarray:
        """Capture a single frame from the desktop.

        When using DXcam, the method retries up to
        :attr:`_MAX_GRAB_RETRIES` times with a short sleep between
        attempts (DXcam can return *None* when no new frame is ready).

        Returns:
            A BGR ``numpy.ndarray`` of shape ``(height, width, 3)``.

        Raises:
            RuntimeError: If no frame could be obtained after all retries
                or if the backend has not been connected.
        """
        if self._using_dxcam:
            return self._grab_dxcam()
        return self._grab_mss()

    def disconnect(self) -> None:
        """Release capture resources."""
        if self._camera is not None:
            try:
                del self._camera
            except Exception:
                logger.debug("Error deleting DXcam camera.", exc_info=True)
            self._camera = None
            logger.info("DXcam camera released.")

        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                logger.debug("Error closing mss instance.", exc_info=True)
            self._sct = None
            logger.info("mss capture released.")

        self._resolution_cache = None

    @property
    def resolution(self) -> tuple[int, int]:
        """Return ``(width, height)`` of the capture area.

        If a region was specified the resolution reflects that region;
        otherwise the full monitor dimensions are returned.

        Raises:
            RuntimeError: If the backend has not been connected yet.
        """
        if self._resolution_cache is not None:
            return self._resolution_cache

        if self._region is not None:
            left, top, right, bottom = self._region
            self._resolution_cache = (right - left, bottom - top)
            return self._resolution_cache

        # Derive from the backend.
        if self._using_dxcam and self._camera is not None:
            # DXcam exposes monitor width/height on the output device.
            width: int = self._camera.width
            height: int = self._camera.height
            self._resolution_cache = (width, height)
            return self._resolution_cache

        if self._sct is not None:
            monitor: dict[str, int] = self._sct.monitors[self._monitor_index + 1]
            self._resolution_cache = (monitor["width"], monitor["height"])
            return self._resolution_cache

        raise RuntimeError(
            "Resolution unknown — call connect() before accessing resolution.",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _grab_dxcam(self) -> np.ndarray:
        """Grab a frame via DXcam with retry logic.

        Returns:
            A BGR ``numpy.ndarray``.

        Raises:
            RuntimeError: If the camera is not initialised or all retries
                are exhausted.
        """
        if self._camera is None:
            raise RuntimeError("DXcam camera is not initialised. Call connect() first.")

        t_start: float = time.perf_counter()

        for attempt in range(1, self._MAX_GRAB_RETRIES + 1):
            frame: np.ndarray | None = self._camera.grab(region=self._region)
            if frame is not None:
                elapsed_ms: float = (time.perf_counter() - t_start) * 1000.0
                logger.debug(
                    "DXcam grab succeeded on attempt %d in %.1f ms.",
                    attempt,
                    elapsed_ms,
                )
                return frame
            logger.debug(
                "DXcam grab returned None (attempt %d/%d); retrying …",
                attempt,
                self._MAX_GRAB_RETRIES,
            )
            time.sleep(self._GRAB_RETRY_DELAY)

        raise RuntimeError(
            f"DXcam failed to capture a frame after {self._MAX_GRAB_RETRIES} attempts.",
        )

    def _grab_mss(self) -> np.ndarray:
        """Grab a frame via mss and convert to BGR.

        Returns:
            A BGR ``numpy.ndarray``.

        Raises:
            RuntimeError: If mss is not initialised.
        """
        if self._sct is None:
            raise RuntimeError("mss is not initialised. Call connect() first.")

        t_start: float = time.perf_counter()

        if self._region is not None:
            left, top, right, bottom = self._region
            monitor: dict[str, int] = {
                "left": left,
                "top": top,
                "width": right - left,
                "height": bottom - top,
            }
        else:
            # mss.monitors[0] is the virtual screen; per-monitor is 1-indexed.
            monitor = self._sct.monitors[self._monitor_index + 1]

        sct_img = self._sct.grab(monitor)
        # mss returns BGRA — drop the alpha channel.
        frame: np.ndarray = np.array(sct_img, dtype=np.uint8)[:, :, :3].copy()

        elapsed_ms: float = (time.perf_counter() - t_start) * 1000.0
        logger.debug("mss grab completed in %.1f ms.", elapsed_ms)

        return frame
