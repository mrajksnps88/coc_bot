from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import cv2

logger = logging.getLogger(__name__)

@dataclass
class MatchResult:
    """Single template match result."""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    template_name: str
    
    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

class TemplateMatcher:
    def __init__(self, template_dir: Path, threshold: float = 0.8, grayscale: bool = True):
        self._templates: dict[str, np.ndarray] = {}
        self._template_dir = template_dir
        self._threshold = threshold
        self._grayscale = grayscale
        
    def load_template(self, name: str, path: Path) -> None:
        """Load a single template image and cache it."""
        if not path.exists():
            logger.warning(f"Template not found: {path}")
            return
        
        img = cv2.imread(str(path))
        if img is None:
            logger.warning(f"Failed to read template: {path}")
            return
            
        if self._grayscale:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
        self._templates[name] = img
        logger.debug(f"Loaded template '{name}' ({img.shape[1]}x{img.shape[0]})")
        
    def load_templates_from_dir(self, directory: Path, recursive: bool = True) -> int:
        """Load all .png templates from directory. Returns count loaded."""
        if not directory.exists():
            logger.warning(f"Template directory not found: {directory}")
            return 0
            
        count = 0
        pattern = "**/*.png" if recursive else "*.png"
        for path in directory.glob(pattern):
            name = path.stem
            self.load_template(name, path)
            count += 1
            
        logger.info(f"Loaded {count} templates from {directory}")
        return count
        
    def match_single(self, screen: np.ndarray, template_name: str, 
                     region: tuple[int, int, int, int] | None = None,
                     threshold: float | None = None) -> MatchResult | None:
        """Find best match for a single template. Returns None if below threshold."""
        if template_name not in self._templates:
            logger.warning(f"Template '{template_name}' not loaded")
            return None
            
        thresh = threshold if threshold is not None else self._threshold
        template = self._templates[template_name]
        th, tw = template.shape[:2]
        
        search_area = screen
        offset_x, offset_y = 0, 0
        
        if region is not None:
            rx, ry, rw, rh = region
            search_area = screen[ry:ry+rh, rx:rx+rw]
            offset_x, offset_y = rx, ry
            
        if self._grayscale and len(search_area.shape) == 3:
            search_area = cv2.cvtColor(search_area, cv2.COLOR_BGR2GRAY)
            
        if search_area.shape[0] < th or search_area.shape[1] < tw:
            return None
            
        result = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= thresh:
            return MatchResult(
                x=max_loc[0] + offset_x,
                y=max_loc[1] + offset_y,
                width=tw,
                height=th,
                confidence=max_val,
                template_name=template_name
            )
        return None

    def match_all(self, screen: np.ndarray, template_name: str,
                  region: tuple[int, int, int, int] | None = None,
                  threshold: float | None = None) -> list[MatchResult]:
        """Find ALL matches above threshold. Apply NMS to remove duplicates."""
        if template_name not in self._templates:
            logger.warning(f"Template '{template_name}' not loaded")
            return []
            
        thresh = threshold if threshold is not None else self._threshold
        template = self._templates[template_name]
        th, tw = template.shape[:2]
        
        search_area = screen
        offset_x, offset_y = 0, 0
        
        if region is not None:
            rx, ry, rw, rh = region
            search_area = screen[ry:ry+rh, rx:rx+rw]
            offset_x, offset_y = rx, ry
            
        if self._grayscale and len(search_area.shape) == 3:
            search_area = cv2.cvtColor(search_area, cv2.COLOR_BGR2GRAY)
            
        if search_area.shape[0] < th or search_area.shape[1] < tw:
            return []
            
        result = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= thresh)
        
        matches = []
        for pt in zip(*locations[::-1]):
            matches.append(MatchResult(
                x=int(pt[0]) + offset_x,
                y=int(pt[1]) + offset_y,
                width=tw,
                height=th,
                confidence=float(result[pt[1], pt[0]]),
                template_name=template_name
            ))
            
        return self._apply_nms(matches)

    def match_multi_scale(self, screen: np.ndarray, template_name: str,
                          scale_range: tuple[float, float, int] = (0.8, 1.2, 10),
                          region: tuple[int, int, int, int] | None = None,
                          threshold: float | None = None) -> MatchResult | None:
        """Multi-scale template matching. Tries multiple scales and returns best."""
        if template_name not in self._templates:
            return None
            
        thresh = threshold if threshold is not None else self._threshold
        template = self._templates[template_name]
        
        best_match = None
        min_scale, max_scale, num_steps = scale_range
        scales = np.linspace(min_scale, max_scale, num_steps)
        
        for scale in scales:
            # Resize template (faster than resizing screen)
            tw = int(template.shape[1] * scale)
            th = int(template.shape[0] * scale)
            
            if tw <= 0 or th <= 0:
                continue
                
            resized_template = cv2.resize(template, (tw, th))
            
            # Temporarily replace template and use match_single
            original_template = self._templates[template_name]
            self._templates[template_name] = resized_template
            
            match = self.match_single(screen, template_name, region, thresh)
            
            self._templates[template_name] = original_template
            
            if match and (best_match is None or match.confidence > best_match.confidence):
                best_match = match
                
        return best_match

    def match_any(self, screen: np.ndarray, template_names: list[str],
                  **kwargs) -> MatchResult | None:
        """Try matching any of the given templates, return first match found."""
        for name in template_names:
            match = self.match_single(screen, name, **kwargs)
            if match:
                return match
        return None

    def _apply_nms(self, matches: list[MatchResult], overlap_thresh: float = 0.3) -> list[MatchResult]:
        """Non-Maximum Suppression to remove overlapping detections."""
        if not matches:
            return []
            
        # Sort by confidence
        matches = sorted(matches, key=lambda m: m.confidence, reverse=True)
        
        keep = []
        while matches:
            best = matches.pop(0)
            keep.append(best)
            
            # Calculate IoU with remaining matches
            remaining = []
            for m in matches:
                # Intersection
                x1 = max(best.x, m.x)
                y1 = max(best.y, m.y)
                x2 = min(best.x + best.width, m.x + m.width)
                y2 = min(best.y + best.height, m.y + m.height)
                
                iw = max(0, x2 - x1)
                ih = max(0, y2 - y1)
                inter_area = iw * ih
                
                # Union
                best_area = best.width * best.height
                m_area = m.width * m.height
                union_area = best_area + m_area - inter_area
                
                iou = inter_area / union_area if union_area > 0 else 0
                
                if iou <= overlap_thresh:
                    remaining.append(m)
                    
            matches = remaining
            
        return keep
