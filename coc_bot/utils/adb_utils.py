"""ADB connection management via ``ppadb``.

Provides the :class:`ADBConnection` class for connecting to an Android device,
executing shell commands, and reconnecting with exponential backoff.  Supports
usage as a context manager.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from ppadb.client import Client as AdbClient
from ppadb.device import Device

if TYPE_CHECKING:
    from types import TracebackType

    from coc_bot.config.settings import ADBSettings

logger: logging.Logger = logging.getLogger(__name__)


class ADBConnection:
    """Manage a connection to a single Android device over ADB.

    Args:
        settings: An :class:`ADBSettings` instance containing ``host``,
                  ``port``, and ``device_serial`` fields.
    """

    def __init__(self, settings: ADBSettings) -> None:
        self._settings: ADBSettings = settings
        self._client: AdbClient | None = None
        self._device: Device | None = None

    # -- connection lifecycle --------------------------------------------------

    def connect(self) -> None:
        """Establish a connection to the ADB server and locate the device."""
        logger.info(
            "Connecting to ADB server at %s:%s",
            self._settings.server_host,
            self._settings.server_port,
        )
        try:
            self._client = AdbClient(
                host=self._settings.server_host,
                port=self._settings.server_port,
            )
            
            # Important: Tell the local ADB server to connect to the emulator instance
            logger.info(f"Connecting ADB server to emulator at {self._settings.device_address}")
            import subprocess
            subprocess.run(["adb", "connect", self._settings.device_address], capture_output=True)
            
            devices: list[Device] = self._client.devices()
        except Exception as exc:
            logger.error("Failed to connect to ADB server: %s", exc)
            raise RuntimeError(
                f"Could not connect to ADB server at "
                f"{self._settings.server_host}:{self._settings.server_port}"
            ) from exc

        if not devices:
            raise RuntimeError("No ADB devices found")

        # If a specific serial was configured, look for it; otherwise take the
        # first available device.
        serial: str | None = getattr(self._settings, "device_serial", None)
        if serial:
            for dev in devices:
                if dev.serial == serial:
                    self._device = dev
                    break
            if self._device is None:
                available: list[str] = [d.serial for d in devices]
                raise RuntimeError(
                    f"Device '{serial}' not found. "
                    f"Available devices: {available}"
                )
        else:
            self._device = devices[0]

        logger.info("Connected to device: %s", self._device.serial)

    def reconnect(self, max_retries: int = 3) -> None:
        """Attempt to reconnect with exponential backoff.

        The delays between retries are 1 s, 2 s, 4 s, … (doubling each time).

        Args:
            max_retries: Maximum number of reconnection attempts.

        Raises:
            RuntimeError: If all retry attempts fail.
        """
        delay: float = 1.0
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            logger.warning(
                "Reconnect attempt %d/%d (waiting %.1fs)",
                attempt,
                max_retries,
                delay,
            )
            time.sleep(delay)
            try:
                self.disconnect()
                self.connect()
                logger.info("Reconnected successfully on attempt %d", attempt)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.error("Reconnect attempt %d failed: %s", attempt, exc)
                delay *= 2

        raise RuntimeError(
            f"Failed to reconnect after {max_retries} attempts"
        ) from last_error

    def disconnect(self) -> None:
        """Clean up the current connection state."""
        if self._device is not None:
            logger.info("Disconnecting from device: %s", self._device.serial)
        self._device = None
        self._client = None

    # -- queries ---------------------------------------------------------------

    def is_connected(self) -> bool:
        """Return ``True`` if a device reference is currently held."""
        return self._device is not None

    def get_device(self) -> Device:
        """Return the connected :class:`Device`.

        Raises:
            RuntimeError: If no device is currently connected.
        """
        if self._device is None:
            raise RuntimeError(
                "No device connected. Call connect() first."
            )
        return self._device

    # -- command execution -----------------------------------------------------

    def execute(self, command: str) -> str:
        """Run a shell command on the connected device.

        Args:
            command: The shell command string to execute.

        Returns:
            The command's standard output as a string.

        Raises:
            RuntimeError: If no device is connected or the command fails.
        """
        device: Device = self.get_device()
        logger.debug("Executing command: %s", command)
        try:
            result: str | None = device.shell(command)
            output: str = result if result is not None else ""
            logger.debug("Command output: %s", output[:200])
            return output
        except Exception as exc:
            logger.error("Command execution failed: %s", exc)
            raise RuntimeError(
                f"Failed to execute command '{command}': {exc}"
            ) from exc

    # -- context manager -------------------------------------------------------

    def __enter__(self) -> ADBConnection:
        """Enter the runtime context and connect to the device."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the runtime context and disconnect."""
        self.disconnect()

def test_connection() -> None:
    """Test the ADB connection."""
    from coc_bot.config.settings import ADBSettings
    settings = ADBSettings()
    
    # Configure logging for the test to output to console
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    adb = ADBConnection(settings)
    logger.info(f"Testing ADB connection via server at {settings.server_host}:{settings.server_port}...")
    try:
        adb.connect()
        logger.info(f"Success! Connected to device: {adb.get_device().serial}")
        output = adb.execute("echo 'Hello from Android Shell!'")
        logger.info(f"Test command output: {output.strip()}")
        adb.disconnect()
    except Exception as e:
        logger.error(f"Test failed: {e}")

