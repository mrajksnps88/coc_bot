"""Abstract interface for screen capture backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np


class CaptureInterface(ABC):
    """Abstract interface for screen capture backends.

    All capture implementations must subclass this and provide
    connect/grab/disconnect/resolution.
    """

    @abstractmethod
    def connect(self) -> None:
        """Initialize the capture backend."""
        ...

    @abstractmethod
    def grab(self) -> np.ndarray:
        """Capture the current screen frame.

        Returns:
            BGR numpy array of the captured frame.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Release resources held by the capture backend."""
        ...

    @property
    @abstractmethod
    def resolution(self) -> tuple[int, int]:
        """Return (width, height) of the capture area."""
        ...

    def __enter__(self) -> CaptureInterface:
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.disconnect()
