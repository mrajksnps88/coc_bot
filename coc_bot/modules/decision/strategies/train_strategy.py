from __future__ import annotations
import logging
import numpy as np
import time

from coc_bot.modules.decision.engine import Strategy, Action
from coc_bot.modules.vision.detector import GameDetector
from coc_bot.core.state_machine import BotStateMachine
from coc_bot.config.settings import BotSettings

logger = logging.getLogger(__name__)

class TrainStrategy(Strategy):
    """Open barracks and queue troops via quick train."""
    
    def __init__(self, settings: BotSettings):
        self._settings = settings
        self._step = 0
        self._last_action_time = 0.0
        
    def process(self, frame: np.ndarray, detector: GameDetector,
                state_machine: BotStateMachine) -> Action | None:
        
        # We need a small delay between steps
        now = time.time()
        if now - self._last_action_time < 2.0:
            return Action('wait', {}, "Waiting for menu animation")
            
        if self._step == 0:
            # 1. Click the main train button
            btn_train = detector.find_button(frame, "train_button")
            if btn_train:
                self._step = 1
                self._last_action_time = now
                return Action('tap', {'x': btn_train.center[0], 'y': btn_train.center[1]}, "Tap Train Button")
            else:
                logger.warning("Could not find train button, returning to main village.")
                state_machine.training_started()
                
        elif self._step == 1:
            # 2. Click the 'Saved Recipes' tab
            btn_tab = detector.find_button(frame, "saved_recipes_tab")
            if btn_tab:
                self._step = 2
                self._last_action_time = now
                return Action('tap', {'x': btn_tab.center[0], 'y': btn_tab.center[1]}, "Tap Saved Recipes Tab")
            else:
                logger.warning("Could not find Saved Recipes tab, trying to proceed anyway.")
                self._step = 2
                
        elif self._step == 2:
            # 3. Click Quick Train (or specifically the Train/Use button inside the tab)
            btns_quick = detector.find_all_buttons(frame, "quick_train_button")
            if btns_quick:
                # Sort buttons from top to bottom
                btns_quick.sort(key=lambda b: b.y)
                
                # Pick the requested army index (or the last one if index is out of bounds)
                target_idx = min(self._settings.farming.train_army_index, len(btns_quick) - 1)
                btn = btns_quick[target_idx]
                
                self._step = 3
                self._last_action_time = now
                return Action('tap', {'x': btn.center[0], 'y': btn.center[1]}, f"Tap Quick Train (Army {target_idx + 1})")
            else:
                logger.info("Assuming Quick Train complete or button missing, closing menu.")
                self._step = 3
                
        elif self._step == 3:
            # 4. Close the menu (we can just tap outside the window or click X)
            # Tapping the top right corner is usually safe, or we just transition and let it close
            self._last_action_time = now
            state_machine.training_started()
            self.reset()
            # Click top right corner to close the training window
            h, w = frame.shape[:2]
            return Action('tap', {'x': w - 50, 'y': 50}, "Close Training Menu")
            
        return None
        
    def reset(self) -> None:
        self._step = 0
