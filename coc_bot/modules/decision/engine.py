from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
import numpy as np

from coc_bot.modules.input.base import InputInterface
from coc_bot.modules.vision.detector import GameDetector, GameState
from coc_bot.core.state_machine import BotStateMachine
from coc_bot.config.settings import BotSettings

logger = logging.getLogger(__name__)

@dataclass
class Action:
    """Represents a bot action to execute."""
    action_type: str  # 'tap', 'swipe', 'wait'
    params: dict
    description: str
    
    def execute(self, input_handler: InputInterface) -> None:
        """Execute this action via the input handler."""
        if self.action_type == 'tap':
            input_handler.tap(self.params['x'], self.params['y'])
        elif self.action_type == 'multi_tap':
            input_handler.multi_tap(self.params['points'])
        elif self.action_type == 'long_press':
            input_handler.long_press(self.params['x'], self.params['y'], self.params.get('duration_ms', 1000))
        elif self.action_type == 'swipe':
            input_handler.swipe(
                self.params['x1'], self.params['y1'],
                self.params['x2'], self.params['y2'],
                self.params.get('duration_ms', 300),
                self.params.get('hold_before_swipe_ms', 0)
            )
        elif self.action_type == 'wait':
            pass
        else:
            logger.warning(f"Unknown action type: {self.action_type}")

class Strategy(ABC):
    """Base class for per-state strategy."""
    
    @abstractmethod
    def process(self, frame: np.ndarray, detector: GameDetector,
                state_machine: BotStateMachine) -> Action | None:
        pass
        
    @abstractmethod
    def reset(self) -> None:
        pass

class DecisionEngine:
    def __init__(self, detector: GameDetector, settings: BotSettings):
        self._strategies: dict[str, Strategy] = {}
        self._detector = detector
        self._settings = settings
        
        # Strategies will be registered here or externally
        
    def register_strategy(self, state: str, strategy: Strategy) -> None:
        self._strategies[state] = strategy
        
    def process(self, frame: np.ndarray, detected_state: GameState,
                state_machine: BotStateMachine) -> Action | None:
        """Main decision method."""
        
        # 1. Update state machine if detection is strong and differs from current
        current_state_str = state_machine.current
        
        if detected_state == GameState.DISCONNECTED and current_state_str != 'disconnected':
            state_machine.connection_lost()
        elif detected_state == GameState.LOADING and current_state_str != 'loading':
            if current_state_str == 'disconnected':
                state_machine.reconnecting()
        elif detected_state == GameState.MAIN_VILLAGE and current_state_str in ('loading', 'disconnected'):
            state_machine.home_detected()
        elif detected_state == GameState.BATTLE_END and current_state_str == 'battle':
            state_machine.battle_over()
            
        # 2. Get strategy for current state
        strategy = self._strategies.get(state_machine.current)
            
        if not strategy:
            logger.debug(f"No strategy for state: {state_machine.current}")
            return None
            
        # 3. Let strategy decide action
        return strategy.process(frame, self._detector, state_machine)
