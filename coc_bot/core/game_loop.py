from __future__ import annotations
import logging
import time
import numpy as np

from coc_bot.modules.capture.base import CaptureInterface
from coc_bot.modules.vision.detector import GameDetector, GameState
from coc_bot.modules.input.base import InputInterface
from coc_bot.modules.decision.engine import DecisionEngine
from coc_bot.core.state_machine import BotStateMachine
from coc_bot.config.settings import BotSettings
from coc_bot.utils.timing import wait_for_change

logger = logging.getLogger(__name__)

class GameLoop:
    def __init__(self, capturer: CaptureInterface, detector: GameDetector,
                 input_handler: InputInterface, decision_engine: DecisionEngine,
                 state_machine: BotStateMachine, settings: BotSettings):
        self._capturer = capturer
        self._detector = detector
        self._input_handler = input_handler
        self._decision_engine = decision_engine
        self._state_machine = state_machine
        self._settings = settings
        
        self._running = False
        self._paused = False
        self._frame_count = 0
        self._last_frame: np.ndarray | None = None
        
    def start(self) -> None:
        """Start the game loop in the current thread."""
        logger.info("Starting game loop...")
        self._running = True
        while self._running:
            if self._paused:
                time.sleep(0.5)
                continue
                
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Error in game loop tick: {e}", exc_info=True)
                time.sleep(1.0)
                
    def _tick(self) -> None:
        """Single iteration: capture → analyze → decide → act → wait"""
        # 1. Capture
        frame = self._capturer.grab()
        if frame is None:
            logger.warning("Failed to grab frame")
            time.sleep(1.0)
            return
            
        self._last_frame = frame
        self._frame_count += 1
        
        # 2. Analyze — detect current game state
        detected_state = self._detector.detect_game_state(frame)
        logger.info(
            "[Tick %d] Detected: %s | State Machine: %s",
            self._frame_count, detected_state.name, self._state_machine.current,
        )
        
        # 3. Decide — let decision engine determine action
        action = self._decision_engine.process(frame, detected_state, self._state_machine)
        
        # 4. Act — execute the action
        if action:
            if self._settings.dry_run:
                logger.info("[DRY RUN] Would execute: %s", action.description)
            else:
                logger.info("Executing action: %s", action.description)
                action.execute(self._input_handler)
        else:
            logger.debug("[Tick %d] No action to take", self._frame_count)
                
        # 5. Wait
        self._smart_wait()
        
    def _smart_wait(self) -> None:
        """Wait before next tick."""
        time.sleep(self._settings.timing.capture_interval)
        
    def stop(self) -> None:
        logger.info("Stopping game loop...")
        self._running = False
        
    def pause(self) -> None:
        logger.info("Pausing game loop...")
        self._paused = True
        
    def resume(self) -> None:
        logger.info("Resuming game loop...")
        self._paused = False
