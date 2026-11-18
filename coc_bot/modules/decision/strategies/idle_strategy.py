from __future__ import annotations
import logging
import time
import numpy as np

from coc_bot.modules.decision.engine import Strategy, Action
from coc_bot.modules.vision.detector import GameDetector
from coc_bot.core.state_machine import BotStateMachine
from coc_bot.utils.timing import Cooldown

logger = logging.getLogger(__name__)

class IdleStrategy(Strategy):
    """Wait and periodically check for things to do."""
    
    def __init__(self, check_interval_s: float = 60.0):
        self._check_cooldown = Cooldown(check_interval_s)
        self._check_cooldown.reset()  # Reset so it waits before first check
        
    def process(self, frame: np.ndarray, detector: GameDetector,
                state_machine: BotStateMachine) -> Action | None:
        
        if self._check_cooldown.is_ready():
            logger.info("Idle check timeout reached, waking up to check village...")
            self._check_cooldown.reset()
            state_machine.wake_up()
            return None
            
        # Optional: check if attacked while idle or disconnected
        
        return Action(
            action_type='wait',
            params={},
            description="Idling..."
        )
        
    def reset(self) -> None:
        self._check_cooldown.reset()
