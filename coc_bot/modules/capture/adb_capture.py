"""ADB-based screen capture backend for Android devices."""
from __future__ import annotations

import io
import logging
import time
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from coc_bot.modules.capture.base import CaptureInterface

if TYPE_CHECKING:
    from coc_bot.config.settings import ADBSettings
    from coc_bot.utils.adb_utils import ADBConnection

logger: logging.Logger = logging.getLogger(__name__)


class ADBCapture(CaptureInterface):
    """Screen capture backend that uses ADB ``screencap`` over USB/Wi-Fi.

    This backend delegates device communication to an
    :class:`~coc_bot.utils.adb_utils.ADBConnection` instance and converts
    the raw PNG output of ``adb exec-out screencap -p`` into BGR numpy
    arrays suitable for OpenCV processing.

    Parameters:
        settings: ADB configuration containing device serial, host, port,
            and any other connection parameters.
    """

    def __init__(self, settings: ADBSettings, connection: ADBConnection | None = None) -> None:
        from coc_bot.utils.adb_utils import ADBConnection

        self._settings: ADBSettings = settings
        self._connection: ADBConnection = connection if connection else ADBConnection(settings)
        self._last_frame: np.ndarray | None = None
        self._resolution: tuple[int, int] | None = None

    # ------------------------------------------------------------------
    # CaptureInterface implementation
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Establish a connection to the ADB device.

        Raises:
            ConnectionError: If the device cannot be reached.
        """
        logger.info("Connecting to ADB device via %s …", self._settings)
        self._connection.connect()
        logger.info("ADB device connected successfully.")

    def grab(self) -> np.ndarray:
        """Capture a single frame from the connected device.

        The method executes ``adb exec-out screencap -p`` to obtain a PNG
        screenshot, converts it to a BGR numpy array, and caches the
        result in :attr:`_last_frame`.

        If the initial capture fails (e.g. due to a transient connection
        drop), a single reconnect-and-retry is attempted before raising.

        Returns:
            A BGR ``numpy.ndarray`` of shape ``(height, width, 3)``.

        Raises:
            RuntimeError: If the frame cannot be captured after one retry.
        """
        try:
            frame: np.ndarray = self._screencap()
        except Exception:
            logger.warning(
                "ADB screencap failed; attempting reconnect …", exc_info=True,
            )
            try:
                self._connection.disconnect()
                self._connection.connect()
                frame = self._screencap()
            except Exception as exc:
                raise RuntimeError(
                    "ADB screencap failed after reconnect attempt.",
                ) from exc

        self._last_frame = frame

        # Cache the resolution from the first successful frame.
        if self._resolution is None:
            height, width = frame.shape[:2]
            self._resolution = (width, height)
            logger.debug("Detected device resolution: %dx%d", width, height)

        return frame

    def disconnect(self) -> None:
        """Disconnect from the ADB device and release resources."""
        logger.info("Disconnecting ADB capture …")
        self._connection.disconnect()
        self._last_frame = None
        logger.info("ADB capture disconnected.")

    @property
    def resolution(self) -> tuple[int, int]:
        """Return the ``(width, height)`` of the captured frame.

        The value is derived from the first successfully captured frame
        and cached for subsequent calls.

        Raises:
            RuntimeError: If no frame has been captured yet.
        """
        if self._resolution is None:
            raise RuntimeError(
                "Resolution unknown — capture at least one frame first.",
            )
        return self._resolution

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _screencap(self) -> np.ndarray:
        """Capture the screen via ``adb exec-out screencap -p``.

        Uses subprocess exclusively and aggressively reconnects before each
        attempt to work around the Google Play Games Developer Emulator's
        habit of dropping ADB connections.

        Returns:
            A BGR ``numpy.ndarray`` of shape ``(height, width, 3)``.

        Raises:
            RuntimeError: If the screencap fails after all retry attempts.
        """
        import subprocess

        device_addr: str = self._settings.device_address
        last_error: str = ""

        for attempt in range(3):
            try:
                # Force a fresh connection every time
                subprocess.run(
                    ["adb", "disconnect", device_addr],
                    capture_output=True, timeout=5,
                )
                subprocess.run(
                    ["adb", "connect", device_addr],
                    capture_output=True, timeout=5,
                )

                # Give the device time to transition from offline → device
                time.sleep(1.5 + attempt)

                t_start: float = time.perf_counter()

                result = subprocess.run(
                    ["adb", "-s", device_addr, "exec-out", "screencap", "-p"],
                    capture_output=True,
                    timeout=15,
                )

                if result.returncode == 0 and len(result.stdout) > 100:
                    raw_bytes: bytes = result.stdout
                    image: Image.Image = Image.open(io.BytesIO(raw_bytes))
                    frame: np.ndarray = np.array(
                        image.convert("RGB")
                    )[:, :, ::-1].copy()

                    elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                    logger.debug(
                        "ADB screencap completed in %.1f ms (attempt %d)",
                        elapsed_ms, attempt + 1,
                    )
                    return frame

                last_error = result.stderr.decode("utf-8", errors="replace")
                logger.warning(
                    "Screencap attempt %d failed: %s", attempt + 1, last_error,
                )

            except subprocess.TimeoutExpired:
                last_error = "timeout"
                logger.warning("Screencap attempt %d timed out", attempt + 1)
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Screencap attempt %d error: %s", attempt + 1, exc,
                )

        raise RuntimeError(
            f"ADB screencap failed after 3 attempts. Last error: {last_error}"
        )

