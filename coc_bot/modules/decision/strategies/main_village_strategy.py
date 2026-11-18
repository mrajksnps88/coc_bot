from __future__ import annotations
import logging
import numpy as np

from coc_bot.modules.decision.engine import Strategy, Action
from coc_bot.modules.vision.detector import GameDetector
from coc_bot.core.state_machine import BotStateMachine
from coc_bot.config.settings import BotSettings

logger = logging.getLogger(__name__)

class MainVillageStrategy(Strategy):
    """Orchestrates actions when in the main village."""
    
    def __init__(self, settings: BotSettings):
        self._settings = settings
        self._state = 'check_collectors'
        self._attacks_done = 0
        
    def process(self, frame: np.ndarray, detector: GameDetector,
                state_machine: BotStateMachine) -> Action | None:
        
        if self._state == 'check_collectors':
            # 1. Are there collectors?
            collectors = detector.find_collectors(frame)
            if collectors:
                logger.info("Found %d collector(s). Transitioning to collect.", len(collectors))
                state_machine.collectors_ready()
                # We return an idle action so the next tick processes the collection state
                self._state = 'train_troops'
                return Action('wait', {}, "Transitioning to Collect")
            
            # If no collectors, move to training
            logger.info("No collectors to tap.")
            self._state = 'train_troops'
            
        if self._state == 'train_troops':
            # 2. Transition to training
            logger.info("Transitioning to train troops.")
            state_machine.army_incomplete()
            self._state = 'upgrade_walls'
            return Action('wait', {}, "Transitioning to Train Troops")
            
        if self._state == 'upgrade_walls':
            # 2.5 Check auto wall
            if self._settings.auto_wall.enabled and not getattr(self, '_wall_checked', False):
                self._wall_checked = True
                logger.info("Checking auto-wall upgrade.")
                state_machine.excess_loot()
                self._state = 'attack'
                return Action('wait', {}, "Transitioning to Upgrade Walls")
            self._state = 'attack'
            
        if self._state == 'attack':
            # 3. Transition to find match
            if self._attacks_done < self._settings.farming.max_attacks_per_session:
                logger.info("Transitioning to find match.")
                state_machine.army_ready()
                self._attacks_done += 1
                self._state = 'check_collectors' # Reset for next cycle
                return Action('wait', {}, "Transitioning to Find Match")
            else:
                self._state = 'done'
                
        if self._state == 'done':
            logger.info("Session complete or max attacks reached. Going idle.")
            state_machine.nothing_to_do()
            
        return None
        
    def reset(self) -> None:
        self._state = 'check_collectors'
        self._wall_checked = False
