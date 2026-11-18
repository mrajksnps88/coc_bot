"""Abstract interface for input automation backends.

Defines the :class:`InputInterface` ABC that every concrete input backend
(ADB, Windows direct-input, …) must implement.  The interface guarantees a
uniform tap / swipe / long-press / text API regardless of the underlying
automation technology.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class InputInterface(ABC):
    """Abstract interface for input backends.

    All input implementations must subclass this and provide
    :meth:`tap`, :meth:`swipe`, :meth:`long_press`, and :meth:`text`
    methods.
    """

    @abstractmethod
    def tap(self, x: int, y: int) -> None:
        """Tap at the given screen coordinates."""
        ...

    @abstractmethod
    def multi_tap(self, points: list[tuple[int, int]]) -> None:
        """Tap multiple points in rapid succession."""
        ...

    @abstractmethod
    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
        hold_before_swipe_ms: int = 0,
    ) -> None:
        """Swipe from ``(x1, y1)`` to ``(x2, y2)``.

        Parameters
        ----------
        x1, y1:
            Start coordinates.
        x2, y2:
            End coordinates.
        duration_ms:
            Duration of the swipe gesture in milliseconds.
        """
        ...

    @abstractmethod
    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        """Long-press at the given coordinates.

        Parameters
        ----------
        x:
            Horizontal pixel coordinate.
        y:
            Vertical pixel coordinate.
        duration_ms:
            How long to hold the press in milliseconds.
        """
        ...

    @abstractmethod
    def text(self, content: str) -> None:
        """Type the given text string.

        Parameters
        ----------
        content:
            The string to type into the currently focused input field.
        """
        ...
