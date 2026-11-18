from __future__ import annotations
import logging
from enum import Enum, auto
from dataclasses import dataclass
import numpy as np

from coc_bot.modules.vision.template_matcher import TemplateMatcher, MatchResult
from coc_bot.modules.vision.color_detector import ColorDetector, ColorDetection
from coc_bot.modules.vision.ocr_reader import OCRReader, OCRResult

logger = logging.getLogger(__name__)

class GameState(Enum):
    UNKNOWN = auto()
    LOADING = auto()
    MAIN_VILLAGE = auto()
    BUILDER_BASE = auto()
    COLLECT_RESOURCES = auto()
    TRAIN_TROOPS = auto()
    FIND_MATCH = auto()
    BATTLE = auto()
    BATTLE_END = auto()
    IDLE = auto()
    DISCONNECTED = auto()

@dataclass
class Detection:
    """A unified detection result."""
    name: str
    x: int
    y: int
    width: int
    height: int
    confidence: float
    method: str  # 'template', 'color', 'ocr'
    
    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

class GameDetector:
    """Unified facade for all vision tasks."""
    
    def __init__(self, template_matcher: TemplateMatcher,
                 color_detector: ColorDetector,
                 ocr_reader: OCRReader | None = None):
        self._templates = template_matcher
        self._colors = color_detector
        self._ocr = ocr_reader
        self._warned_templates: set[str] = set()
        
    @property
    def color_detector(self) -> ColorDetector:
        return self._colors
        
    def _match(self, screen: np.ndarray, name: str) -> MatchResult | None:
        """Match a template, warning only once if it's missing."""
        if name not in self._templates._templates:
            if name not in self._warned_templates:
                logger.warning("Template '%s' not loaded — skipping", name)
                self._warned_templates.add(name)
            return None
        return self._templates.match_single(screen, name)

    def detect_game_state(self, screen: np.ndarray) -> GameState:
        """Determine current game state by checking for key indicators."""
        # Priority 1: Disconnected (Connection Lost / Logged in elsewhere)
        if self._match(screen, "reload_popup") or self._match(screen, "try_again_button"):
            return GameState.DISCONNECTED
            
        # Priority 2: Loading
        if self._match(screen, "loading_screen"):
            return GameState.LOADING
            
        # Priority 3: Battle End
        if self._match(screen, "return_home"):
            return GameState.BATTLE_END
            
        # Priority 4: Battle
        if self._match(screen, "end_battle"):
            return GameState.BATTLE
            
        # Priority 5: Find Match
        if self._match(screen, "next_button"):
            return GameState.FIND_MATCH
            
        # Priority 6: Main Village
        if self._match(screen, "attack_button") or self._match(screen, "home_button"):
            return GameState.MAIN_VILLAGE
            
        return GameState.UNKNOWN

    def find_collectors(self, screen: np.ndarray) -> list[Detection]:
        """Find resource collectors that are ready to collect."""
        detections = []
        height, width = screen.shape[:2]
        
        def is_in_ui_zone(x: int, y: int) -> bool:
            """Check if a coordinate is over a static UI element."""
            # Bottom right (Shop)
            if y > height * 0.75 and x > width * 0.8: return True
            # Bottom left (Attack, Chat)
            if y > height * 0.75 and x < width * 0.2: return True
            # Top right (Resources, Gems, Builders)
            if y < height * 0.25 and x > width * 0.6: return True
            # Top left (Profile, Level)
            if y < height * 0.25 and x < width * 0.3: return True
            return False
            
        # Strictly use Template Matching for collectors.
        # Raw color detection (especially gold) is too noisy because of gold trim
        # on buildings, walls, and UI elements like the Tournament Hub.
        for res in ["gold_full", "elixir_full", "dark_elixir_full"]:
            # Use a much lower threshold (0.6) for collectors because the icons
            # bob up and down, causing the background grass/walls behind them
            # to mismatch strictly.
            matches = self._templates.match_all(screen, res, threshold=0.6)
            for m in matches:
                if is_in_ui_zone(m.center[0], m.center[1]):
                    continue
                detections.append(Detection(
                    name=res, x=m.x, y=m.y, width=m.width, height=m.height,
                    confidence=m.confidence, method="template"
                ))
                
        return detections

    def find_button(self, screen: np.ndarray, button_name: str) -> Detection | None:
        """Find a specific UI button on screen."""
        match = self._templates.match_single(screen, button_name)
        if match:
            return Detection(
                name=button_name, x=match.x, y=match.y, width=match.width, height=match.height,
                confidence=match.confidence, method="template"
            )
        return None

    def find_all_buttons(self, screen: np.ndarray, button_name: str) -> list[Detection]:
        """Find all instances of a specific UI button on screen."""
        matches = self._templates.match_all(screen, button_name)
        return [
            Detection(
                name=button_name, x=m.x, y=m.y, width=m.width, height=m.height,
                confidence=m.confidence, method="template"
            )
            for m in matches
        ]

    def read_resources(self, screen: np.ndarray) -> dict[str, int | None]:
        """Read current resource amounts from the HUD."""
        if not self._ocr:
            return {'gold': None, 'elixir': None, 'dark_elixir': None, 'gems': None}
        return self._ocr.read_resource_bar(screen)

    def read_enemy_loot(self, screen: np.ndarray, regions: dict[str, dict] | None = None) -> dict[str, int | None]:
        """Read available loot during enemy base search."""
        if not self._ocr:
            return {'gold': None, 'elixir': None, 'dark_elixir': None}
        return self._ocr.read_loot_available(screen, regions)

    def is_screen_changed(self, prev: np.ndarray, curr: np.ndarray, 
                          threshold: float = 0.02) -> bool:
        """Check if screen has meaningfully changed between frames."""
        if prev is None or curr is None:
            return True
        if prev.shape != curr.shape:
            return True
            
        # Calculate mean squared error or simple difference
        diff = cv2.absdiff(prev, curr)
        mean_diff = np.mean(diff)
        
        # Normalize to 0-1
        normalized_diff = mean_diff / 255.0
        return normalized_diff > threshold
