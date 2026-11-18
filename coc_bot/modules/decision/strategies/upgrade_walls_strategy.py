"""Strategy for automatically upgrading walls to dump excess loot."""
from __future__ import annotations
import logging
import time

from coc_bot.modules.decision.engine import Strategy, Action
from coc_bot.core.state_machine import BotStateMachine
from coc_bot.config.settings import BotSettings

logger = logging.getLogger(__name__)

class UpgradeWallsStrategy(Strategy):
    def __init__(self, settings: BotSettings):
        self._settings = settings
        self._step = 0
        self._last_action_time = 0
        self._wait_time = 0
        
    def process(self, frame, detector, state_machine: BotStateMachine) -> Action | None:
        now = time.time()
        if now - self._last_action_time < self._wait_time:
            return Action('wait', {}, f"Waiting {self._wait_time}s")
            
        self._last_action_time = now
        self._wait_time = 1.0 # Default wait between taps
        
        import cv2
        import numpy as np
        from coc_bot.modules.vision.ocr_reader import OCRReader
        
        if self._step == 0:
            # Step 0: Check if we have enough loot to upgrade a wall
            logger.info("Reading current loot to check against auto-wall thresholds...")
            if not hasattr(self, '_ocr'):
                self._ocr = OCRReader()
                self._ocr.preload()
                
            gold_val = 0
            elixir_val = 0
            
            if 'own_gold' in self._settings.screen_regions:
                r = self._settings.screen_regions['own_gold']
                res = self._ocr.read_text(frame, region=(r['x'], r['y'], r['width'], r['height']), allowlist='0123456789')
                if res:
                    try:
                        gold_val = int(res[0].text)
                    except: pass
                    
            if 'own_elixir' in self._settings.screen_regions:
                r = self._settings.screen_regions['own_elixir']
                res = self._ocr.read_text(frame, region=(r['x'], r['y'], r['width'], r['height']), allowlist='0123456789')
                if res:
                    try:
                        elixir_val = int(res[0].text)
                    except: pass
                    
            logger.info(f"Read Own Loot: Gold={gold_val}, Elixir={elixir_val}")
            
            can_upgrade_gold = (gold_val >= self._settings.auto_wall.keep_gold + 1_000_000) and self._settings.auto_wall.upgrade_with in ("both", "gold")
            can_upgrade_elixir = (elixir_val >= self._settings.auto_wall.keep_elixir + 1_000_000) and self._settings.auto_wall.upgrade_with in ("both", "elixir")
            
            if not can_upgrade_gold and not can_upgrade_elixir:
                logger.info("Loot is below keep thresholds. Returning to main village.")
                self._step = 4
                return Action('wait', {}, "Preparing to finish wall upgrades")
                
            self._upgrade_type = "elixir" if can_upgrade_elixir else "gold"
            logger.info(f"Upgrading wall with {self._upgrade_type}...")
            self._step = 1
            
            # Tap the isolated wall piece
            return Action('tap', {
                'x': self._settings.auto_wall.wall_x,
                'y': self._settings.auto_wall.wall_y
            }, "Tap isolated wall piece")
            
        elif self._step == 1:
            # Step 1: Click the Elixir or Gold button from the bottom menu
            self._step = 2
            self._wait_time = 1.0 # Wait for the big confirmation dialog to appear
            
            x_coord = None
            y_coord = None
            
            if self._upgrade_type == "gold":
                x_coord = self._settings.auto_wall.btn_gold_x
                y_coord = self._settings.auto_wall.btn_gold_y
            else:
                x_coord = self._settings.auto_wall.btn_elixir_x
                y_coord = self._settings.auto_wall.btn_elixir_y
                
            if x_coord is not None and y_coord is not None:
                return Action('tap', {'x': x_coord, 'y': y_coord}, f"Upgrade with {self._upgrade_type}")
            else:
                logger.warning(f"Could not find coordinates for '{self._upgrade_type}' button! Aborting.")
                state_machine.wall_upgrade_done()
                self._step = 0
                return Action('wait', {}, "Abort upgrade")
                
        elif self._step == 2:
            # Step 2: Click the giant green Confirm button
            self._step = 3 # Go to cleanup step
            self._wait_time = 1.5 # Wait for the upgrade animation to finish
            
            x_coord = self._settings.auto_wall.btn_confirm_x
            y_coord = self._settings.auto_wall.btn_confirm_y
            
            if x_coord is not None and y_coord is not None:
                return Action('tap', {'x': x_coord, 'y': y_coord}, "Confirm final upgrade")
            else:
                logger.warning("Could not find coordinates for final confirm button! Aborting.")
                state_machine.wall_upgrade_done()
                return Action('wait', {}, "Abort upgrade")
                
        elif self._step == 3:
            # Step 3: Dismiss any leftover dialogs (e.g., if we didn't have enough loot)
            # Tapping the wall piece itself is a safe "background" tap that dismisses modal dialogs.
            self._step = 0
            self._wait_time = 1.0
            
            # Increment a safety counter to prevent infinite loops if OCR is misreading loot
            self._upgrade_attempts = getattr(self, '_upgrade_attempts', 0) + 1
            if self._upgrade_attempts > 5:
                logger.warning("Tried to upgrade walls 5 times. Assuming OCR error or out of loot. Aborting.")
                self._upgrade_attempts = 0
                state_machine.wall_upgrade_done()
                return Action('tap', {'x': self._settings.auto_wall.wall_x, 'y': self._settings.auto_wall.wall_y}, "Force exit dialogs")
                
            return Action('tap', {'x': self._settings.auto_wall.wall_x, 'y': self._settings.auto_wall.wall_y}, "Dismiss leftover dialogs")
            
        elif self._step == 4:
            # Step 4: Final cleanup when no more upgrades can be done.
            # Tap the far right edge of the screen to unselect the wall piece and close its bottom menu.
            # If we don't do this, the open menu will block the first tap on the Attack button!
            self._step = 0
            self._wait_time = 1.0
            state_machine.wall_upgrade_done()
            
            h, w = frame.shape[:2]
            # Safe tap at the middle-right edge of the screen
            return Action('tap', {'x': w - 20, 'y': h // 2}, "Unselect wall piece")
            
        return None
        
    def reset(self) -> None:
        self._step = 0
        self._last_action_time = 0
        self._wait_time = 0
