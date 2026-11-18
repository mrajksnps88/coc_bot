from __future__ import annotations
import logging
from dataclasses import dataclass
import numpy as np
import cv2

logger = logging.getLogger(__name__)

@dataclass
class ColorRange:
    """HSV color range definition."""
    name: str
    lower: tuple[int, int, int]
    upper: tuple[int, int, int]

@dataclass
class ColorDetection:
    """Result of color detection."""
    x: int
    y: int
    width: int
    height: int
    area: int
    color_name: str
    
    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

COC_COLORS = {
    # Narrowed gold range to require higher saturation and brightness to ignore wood/trim
    "gold_glow": ColorRange("gold_glow", (20, 180, 180), (30, 255, 255)),
    # Elixir tightened slightly to avoid pink/purple hair and banners
    "elixir_glow": ColorRange("elixir_glow", (140, 150, 150), (165, 255, 255)),
    # Dark elixir is tricky (mostly black/grey), tightened to avoid shadows
    "dark_elixir_glow": ColorRange("dark_elixir_glow", (0, 0, 0), (180, 255, 40)),
    # Narrowed green to catch bright health bars, not grass
    "green_health": ColorRange("green_health", (40, 150, 150), (75, 255, 255)),
    "red_health": ColorRange("red_health", (0, 150, 150), (10, 255, 255)),
    "deploy_zone": ColorRange("deploy_zone", (0, 0, 200), (180, 30, 255)),
}

class ColorDetector:
    # Increased minimum area from 100 to 1000 to ignore small particles/UI
    def __init__(self, min_area: int = 1000):
        self._color_ranges: dict[str, ColorRange] = dict(COC_COLORS)
        self._min_area = min_area
        
    def add_color_range(self, color_range: ColorRange) -> None:
        self._color_ranges[color_range.name] = color_range
        
    def create_mask(self, screen: np.ndarray, color_name: str) -> np.ndarray:
        """Return binary mask for the color range."""
        if color_name not in self._color_ranges:
            logger.warning(f"Color range '{color_name}' not found")
            return np.zeros(screen.shape[:2], dtype=np.uint8)
            
        color_range = self._color_ranges[color_name]
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        
        lower = np.array(color_range.lower, dtype=np.uint8)
        upper = np.array(color_range.upper, dtype=np.uint8)
        
        mask = cv2.inRange(hsv, lower, upper)
        
        # Optional: cleanup noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        return mask
        
    def detect(self, screen: np.ndarray, color_name: str,
               region: tuple[int, int, int, int] | None = None,
               min_area: int | None = None) -> list[ColorDetection]:
        """Detect all regions matching the named color range."""
        area_threshold = min_area if min_area is not None else self._min_area
        
        search_area = screen
        offset_x, offset_y = 0, 0
        if region is not None:
            rx, ry, rw, rh = region
            search_area = screen[ry:ry+rh, rx:rx+rw]
            offset_x, offset_y = rx, ry
            
        mask = self.create_mask(search_area, color_name)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        results = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= area_threshold:
                x, y, w, h = cv2.boundingRect(contour)
                results.append(ColorDetection(
                    x=x + offset_x,
                    y=y + offset_y,
                    width=w,
                    height=h,
                    area=int(area),
                    color_name=color_name
                ))
                
        return results

    def detect_multiple(self, screen: np.ndarray, color_names: list[str],
                        **kwargs) -> dict[str, list[ColorDetection]]:
        """Detect multiple color ranges and return mapped results."""
        results = {}
        for name in color_names:
            results[name] = self.detect(screen, name, **kwargs)
        return results
