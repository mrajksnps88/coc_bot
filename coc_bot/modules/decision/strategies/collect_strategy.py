from __future__ import annotations
import logging
import numpy as np

from coc_bot.modules.decision.engine import Strategy, Action
from coc_bot.modules.vision.detector import GameDetector
from coc_bot.core.state_machine import BotStateMachine

logger = logging.getLogger(__name__)

class CollectStrategy(Strategy):
    """Find and tap ready resource collectors."""
    
    def __init__(self):
        self._collected_count = 0
        self._max_collectors = 20
        
    def process(self, frame: np.ndarray, detector: GameDetector,
                state_machine: BotStateMachine) -> Action | None:
        
        current = state_machine.current
        collectors = detector.find_collectors(frame)
        
        if current == 'main_village':
            # We're on the home screen — check if there are collectors to tap
            if collectors:
                logger.info(
                    "Found %d collector(s) ready! Transitioning to collect.",
                    len(collectors),
                )
                state_machine.collectors_ready()
                # Return the first tap immediately
                target = collectors[0]
                self._collected_count = 1
                return Action(
                    action_type='tap',
                    params={'x': target.center[0], 'y': target.center[1]},
                    description=f"Tap {target.name} at {target.center}",
                )
            else:
                logger.info("No collectors ready. Going idle.")
                state_machine.nothing_to_do()
                return None
        
        elif current == 'collect_resources':
            # Already collecting — keep tapping remaining collectors
            if not collectors or self._collected_count >= self._max_collectors:
                logger.info(
                    "Collection done (%d tapped). Returning to village.",
                    self._collected_count,
                )
                self.reset()
                state_machine.collection_done()
                return None
                
            target = collectors[0]
            self._collected_count += 1
            return Action(
                action_type='tap',
                params={'x': target.center[0], 'y': target.center[1]},
                description=f"Tap {target.name} at {target.center} ({self._collected_count}/{len(collectors)})",
            )
        
        return None
        
    def reset(self) -> None:
        self._collected_count = 0

