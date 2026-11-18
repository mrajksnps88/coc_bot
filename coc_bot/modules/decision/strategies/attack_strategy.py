from __future__ import annotations
import logging
import time
import numpy as np
import cv2

from coc_bot.modules.decision.engine import Strategy, Action
from coc_bot.modules.vision.detector import GameDetector
from coc_bot.core.state_machine import BotStateMachine
from coc_bot.config.settings import BotSettings

logger = logging.getLogger(__name__)

class AttackStrategy(Strategy):
    """Search for base, evaluate loot, deploy troops."""
    
    def __init__(self, settings: BotSettings):
        self._settings = settings
        self.reset()

    def reset(self) -> None:
        self._step = 0
        self._deployment_phase = 0
        self._last_deployment_time = 0.0
        self._menu_step = 0
        self._collectors_to_snipe = []
        self._current_collector_idx = 0
        self._current_troop_idx = 0
        self._current_hero_idx = 0
        
    def process(self, frame: np.ndarray, detector: GameDetector,
                state_machine: BotStateMachine) -> Action | None:
        
        state = state_machine.current
        
        # Self-contained reset: if we just entered find_match from a different state (like main_village)
        if getattr(self, '_last_processed_state', None) != state:
            if state == 'find_match':
                self.reset()
            self._last_processed_state = state
            
        if state == 'find_match':
            # 1. Start the attack sequence (if we are still on the main village screen or menus)
            if getattr(self, '_menu_step', 0) == 0:
                self._menu_step = 1
                self._last_deployment_time = time.time()
                btn_attack = detector.find_button(frame, "attack_button")
                if btn_attack:
                    return Action('tap', {'x': btn_attack.center[0], 'y': btn_attack.center[1]}, "Tap Attack")
                elif "attack_button" in self._settings.screen_regions:
                    region = self._settings.screen_regions["attack_button"]
                    return Action('tap', {'x': region['x'] + region['width'] // 2, 'y': region['y'] + region['height'] // 2}, "Tap Attack (Fallback coords)")
                    
            elif getattr(self, '_menu_step', 0) == 1:
                if time.time() - self._last_deployment_time < 1.5:
                    return Action('wait', {}, "Waiting for find match menu")
                self._menu_step = 2
                self._last_deployment_time = time.time()
                btn_find = detector.find_button(frame, "find_match")
                if btn_find:
                    return Action('tap', {'x': btn_find.center[0], 'y': btn_find.center[1]}, "Tap Find Match")
                elif "find_match" in self._settings.screen_regions:
                    region = self._settings.screen_regions["find_match"]
                    return Action('tap', {'x': region['x'] + region['width'] // 2, 'y': region['y'] + region['height'] // 2}, "Tap Find Match (Fallback coords)")
                    
            elif getattr(self, '_menu_step', 0) == 2:
                if time.time() - self._last_deployment_time < 1.5:
                    return Action('wait', {}, "Waiting for confirm menu")
                self._menu_step = 3
                self._last_deployment_time = time.time()
                btn_confirm = detector.find_button(frame, "confirm_attack")
                if btn_confirm:
                    return Action('tap', {'x': btn_confirm.center[0], 'y': btn_confirm.center[1]}, "Tap Confirm Attack")
                elif "confirm_match" in self._settings.screen_regions:
                    region = self._settings.screen_regions["confirm_match"]
                    return Action('tap', {'x': region['x'] + region['width'] // 2, 'y': region['y'] + region['height'] // 2}, "Tap Confirm Attack (Fallback coords)")
                    
            elif getattr(self, '_menu_step', 0) == 3:
                # Give it some time to load the actual enemy base
                if time.time() - self._last_deployment_time < 4.0:
                    return Action('wait', {}, "Waiting for base to load")
                self._menu_step = 4

            # 2. Evaluate loot (we are on an enemy base)
            now = time.time()
            if now - self._last_deployment_time < 2.0:
                return Action('wait', {}, "Waiting for base to load")

            if detector._ocr:
                loot = detector.read_enemy_loot(frame, self._settings.screen_regions)
                gold = loot.get('gold')
                elixir = loot.get('elixir')
                
                logger.info(f"Detected Loot - Gold: {gold}, Elixir: {elixir}")
                
                min_gold = self._settings.farming.min_gold_loot
                min_elixir = self._settings.farming.min_elixir_loot
                
                # If we couldn't read the numbers, we skip to be safe (or you could change it to attack)
                if gold is not None and elixir is not None:
                    if gold >= min_gold and elixir >= min_elixir:
                        logger.info("Loot requirements met! Starting attack.")
                        state_machine.match_found()
                        return Action('wait', {}, "Transitioning to Battle")
                    else:
                        logger.info("Loot too low, skipping.")
                else:
                    logger.warning("Failed to read loot, skipping base.")
            else:
                logger.warning("OCR disabled. Skipping base by default.")
                
            # If we decide not to attack
            self._last_deployment_time = now
            btn_next = detector.find_button(frame, "next_button")
            if btn_next:
                return Action('tap', {'x': btn_next.center[0], 'y': btn_next.center[1]}, "Tap Next Base")
            return Action('wait', {}, "Waiting for Next button")
            
        elif state == 'battle':
            # 3. Deploy troops
            now = time.time()
            if now - self._last_deployment_time > 1.0:
                self._deployment_phase += 1
                self._last_deployment_time = now
                
                h, w = frame.shape[:2]
                
                if self._settings.farming.attack_style == "spam":
                    slots = self._settings.farming.troop_slots
                    
                    # Legacy fallback if they only have the old single slot configured
                    if not slots and self._settings.farming.troop_slot_x is not None and self._settings.farming.troop_slot_y is not None:
                        slots = [(self._settings.farming.troop_slot_x, self._settings.farming.troop_slot_y)]
                        
                    if not slots:
                        logger.warning("No troop slots configured for spam attack! Waiting...")
                        return Action('wait', {}, "No troop slots configured")
                        
                    if getattr(self, '_current_troop_idx', 0) >= len(slots):
                        hero_slots = getattr(self._settings.farming, 'hero_slots', [])
                        if not hasattr(self, '_current_hero_idx'):
                            self._current_hero_idx = 0
                            self._deployment_phase = 0
                            
                        if self._current_hero_idx < len(hero_slots):
                            hero_x, hero_y = hero_slots[self._current_hero_idx]
                            drop_x, drop_y = int(w*0.5), int(h*0.9)
                            poly = self._settings.screen_regions.get('deploy_polygon', [])
                            if isinstance(poly, list) and len(poly) > 0:
                                drop_pt = poly[self._current_hero_idx % len(poly)]
                                drop_x, drop_y = drop_pt[0], drop_pt[1]
                                
                            if self._deployment_phase == 0:
                                self._deployment_phase = 1
                                return Action('tap', {'x': hero_x, 'y': hero_y}, f"Select Hero {self._current_hero_idx + 1}")
                            elif self._deployment_phase == 1:
                                self._deployment_phase = 2
                                return Action('tap', {'x': drop_x, 'y': drop_y}, f"Deploy Hero {self._current_hero_idx + 1}")
                            else:
                                self._current_hero_idx += 1
                                self._deployment_phase = 0
                                return Action('tap', {'x': hero_x, 'y': hero_y}, f"Activate Hero {self._current_hero_idx} Ability")
                                
                        return Action('wait', {}, "Waiting for battle to end")
                        
                    # We are deploying troop `self._current_troop_idx`
                    if self._deployment_phase == 1:
                        # Select the farming troop
                        troop_x, troop_y = slots[self._current_troop_idx]
                        return Action('tap', {'x': troop_x, 'y': troop_y}, f"Select Spam Troop {self._current_troop_idx + 1}")
                    else:
                        poly = self._settings.screen_regions.get('deploy_polygon', [])
                        edge_idx = self._deployment_phase - 2
                        
                        if isinstance(poly, list) and len(poly) > 1:
                            # Check if the current troop slot is empty
                            # Exhausted slots turn grayscale, so saturation drops significantly
                            troop_x, troop_y = slots[self._current_troop_idx]
                            patch = frame[max(0, troop_y-15):troop_y+15, max(0, troop_x-15):troop_x+15]
                            if patch.size > 0:
                                hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
                                avg_sat = np.mean(hsv[:, :, 1])
                                
                                if avg_sat < 35:
                                    logger.info(f"Troop {self._current_troop_idx + 1} empty (sat={avg_sat:.1f}). Moving to next.")
                                    self._current_troop_idx += 1
                                    self._deployment_phase = 0
                                    return Action('wait', {}, f"Finished troop {self._current_troop_idx}")
                            
                            # Loop over edges infinitely until empty
                            edge_idx = (self._deployment_phase - 2) % len(poly)
                            
                            p1 = poly[edge_idx]
                            p2 = poly[(edge_idx + 1) % len(poly)]
                            
                            # Generate 15 points along this line for a reliable spam
                            num_points = 15
                            points = []
                            for i in range(num_points):
                                fraction = i / max(1, (num_points - 1))
                                px = int(p1[0] + (p2[0] - p1[0]) * fraction)
                                py = int(p1[1] + (p2[1] - p1[1]) * fraction)
                                points.append((px, py))
                                
                            return Action('multi_tap', {'points': points}, f"Spam Edge {edge_idx + 1} (Troop {self._current_troop_idx + 1})")
                        else:
                            # Poly not configured correctly, just move to next troop
                            logger.warning("Deploy polygon not configured correctly.")
                            self._current_troop_idx += 1
                            self._deployment_phase = 0 # reset phase so next loop it taps the next troop
                            return Action('wait', {}, f"Finished deploying troop {self._current_troop_idx}")
                else:
                    # Original Snipe strategy
                    if self._deployment_phase == 1:
                        # Scan the screen for actual pink elixir and gold blobs since bubbles don't appear in battles!
                        # We use min_area=800 to filter out tiny particles (like archer hair or tower trims)
                        colors = detector.color_detector.detect_multiple(frame, ["elixir_glow", "gold_glow"], min_area=800)
                        
                        self._collectors_to_snipe = []
                        self._collectors_to_snipe.extend(colors.get("elixir_glow", []))
                        self._collectors_to_snipe.extend(colors.get("gold_glow", []))
                        
                        logger.info(f"Collector Sniping Strategy: Found {len(self._collectors_to_snipe)} colored resource buildings to target")
                        self._current_collector_idx = 0
                        self._troops_per_collector = 5
                        return Action('wait', {}, "Scanned for collectors via color")
                        
                    elif self._deployment_phase == 2:
                        # Select the farming troop
                        troop_x, troop_y = int(w*0.2), int(h*0.92)
                        if self._settings.farming.troop_slot_x is not None and self._settings.farming.troop_slot_y is not None:
                            troop_x = self._settings.farming.troop_slot_x
                            troop_y = self._settings.farming.troop_slot_y
                                
                        return Action('tap', {'x': troop_x, 'y': troop_y}, "Select Snipe Troop")
                        
                    elif self._deployment_phase >= 3:
                        # If we've sniped all collectors (or didn't find any), we're done
                        if not hasattr(self, '_collectors_to_snipe') or self._current_collector_idx >= len(self._collectors_to_snipe):
                            # Dump remaining troops
                            if self._deployment_phase == 3:
                                drop_x, drop_y = int(w*0.95), int(h*0.5)
                                if 'deploy_polygon' in self._settings.screen_regions:
                                    poly = self._settings.screen_regions['deploy_polygon']
                                    if isinstance(poly, list) and len(poly) > 0:
                                        import random
                                        pt = random.choice(poly)
                                        drop_x, drop_y = pt[0], pt[1]
                                return Action('long_press', {'x': drop_x, 'y': drop_y, 'duration_ms': 2000}, "Dump remaining troops")
                            return Action('wait', {}, "Waiting for battle to end")
                            
                        # Get the current collector
                        collector = self._collectors_to_snipe[self._current_collector_idx]
                        
                        # Calculate drop position: We want to drop directly "behind" the collector.
                        # We do this by calculating the vector from the center of the screen to the collector,
                        # and pushing the drop point further outward along that line.
                        
                        cx, cy = collector.center
                        center_x, center_y = w / 2, h / 2
                        
                        # Vector from base center to collector
                        vx = cx - center_x
                        vy = cy - center_y
                        
                        # Normalize the vector
                        mag = (vx**2 + vy**2)**0.5
                        if mag == 0:
                            mag = 1
                            
                        nvx = vx / mag
                        nvy = vy / mag
                        
                        # Push outward by ~12% of screen width to clear the red zone
                        push_dist = w * 0.12
                        
                        drop_x = int(cx + nvx * push_dist)
                        drop_y = int(cy + nvy * push_dist)
                        
                        # Cap the coordinates to safely stay on screen and avoid HUDs (Legacy Fallback)
                        drop_x = max(int(w * 0.02), min(drop_x, int(w * 0.98)))
                        drop_y = max(int(h * 0.10), min(drop_y, int(h * 0.75)))
                        
                        # Override with N-Point Custom Polygon if defined
                        if 'deploy_polygon' in self._settings.screen_regions:
                            import random
                            poly = self._settings.screen_regions['deploy_polygon']
                            if isinstance(poly, list) and len(poly) >= 3:
                                # Ray intersection: from center_x, center_y through cx, cy
                                x1, y1 = center_x, center_y
                                x2, y2 = cx, cy
                                
                                best_t = -1
                                best_ix, best_iy = None, None
                                
                                for i in range(len(poly)):
                                    p3 = poly[i]
                                    p4 = poly[(i + 1) % len(poly)]
                                    x3, y3 = p3[0], p3[1]
                                    x4, y4 = p4[0], p4[1]
                                    
                                    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
                                    if den != 0:
                                        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
                                        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / den
                                        
                                        # t > 0 means intersection is in the direction of the collector
                                        # 0 <= u <= 1 means intersection lies perfectly on the user's drawn segment
                                        if t > 0 and 0 <= u <= 1:
                                            if best_t == -1 or t < best_t:
                                                # We take the first intersection we hit going outward
                                                best_t = t
                                                best_ix = x1 + t * (x2 - x1)
                                                best_iy = y1 + t * (y2 - y1)
                                                
                                if best_ix is not None and best_iy is not None:
                                    # Add a tiny bit of random jitter (e.g., +/- 10 pixels) to simulate human
                                    drop_x = int(best_ix) + random.randint(-10, 10)
                                    drop_y = int(best_iy) + random.randint(-10, 10)
                            
                        self._current_collector_idx += 1
                        
                        # Dump a cluster of troops near this edge targeting the collector
                        return Action('long_press', {'x': drop_x, 'y': drop_y, 'duration_ms': 2000}, f"Snipe Collector {self._current_collector_idx}")
                
            # Wait for battle to end (detector will transition state to battle_end when return_home appears)
            return Action('wait', {}, "Waiting for battle to end")
            
        elif state == 'battle_end':
            # 4. Return home
            btn_return = detector.find_button(frame, "return_home")
            if btn_return:
                state_machine.return_home()
                self.reset()
                return Action('tap', {'x': btn_return.center[0], 'y': btn_return.center[1]}, "Tap Return Home")
                
        return None
