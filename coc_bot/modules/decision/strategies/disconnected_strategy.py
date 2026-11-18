from __future__ import annotations
import logging
import numpy as np
import time

from coc_bot.modules.decision.engine import Strategy, Action
from coc_bot.modules.vision.detector import GameDetector
from coc_bot.core.state_machine import BotStateMachine

logger = logging.getLogger(__name__)

class DisconnectedStrategy(Strategy):
    """Strategy for clicking the Reload button when disconnected."""
    
    def __init__(self):
        self._last_tap_time = 0.0
        
    def process(self, frame: np.ndarray, detector: GameDetector,
                state_machine: BotStateMachine) -> Action | None:
        
        now = time.time()
        if now - self._last_tap_time < 5.0:
            return Action('wait', {}, "Waiting for game to reload")
            
        # Find the disconnected popup
        match = detector._match(frame, "reload_popup")
        if not match:
            match = detector._match(frame, "try_again_button")
            
        if match:
            self._last_tap_time = now
            return Action('tap', {'x': match.center[0], 'y': match.center[1]}, "Tap Reload Game")
            
        return Action('wait', {}, "Waiting for reload button")
        
    def reset(self) -> None:
        self._last_tap_time = 0.0
