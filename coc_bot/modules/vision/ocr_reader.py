from __future__ import annotations
import logging
from dataclasses import dataclass
import numpy as np
import cv2
import re

logger = logging.getLogger(__name__)

@dataclass
class OCRResult:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int]

class OCRReader:
    def __init__(self, languages: list[str] | None = None, gpu: bool = False):
        self._reader = None
        self._languages = languages or ["en"]
        self._gpu = gpu
        
    def preload(self) -> None:
        """Preload the OCR model into memory."""
        self._ensure_reader()

    def _ensure_reader(self) -> None:
        if self._reader is None:
            logger.info("Initializing EasyOCR reader (may take a moment)...")
            import easyocr
            self._reader = easyocr.Reader(self._languages, gpu=self._gpu)
            
    def read_text(self, image: np.ndarray, 
                  region: tuple[int, int, int, int] | None = None,
                  allowlist: str | None = None) -> list[OCRResult]:
        """Read text from an image using EasyOCR."""
        self._ensure_reader()
        
        search_area = image
        offset_x, offset_y = 0, 0
        if region is not None:
            rx, ry, rw, rh = region
            search_area = image[ry:ry+rh, rx:rx+rw]
            offset_x, offset_y = rx, ry
            
        # Optional: Save for debugging if you want to inspect what the OCR sees
        # cv2.imwrite(f"debug_ocr_crop_{offset_y}_raw.png", search_area)
            
        # Preprocessing: The game font is white with a heavy black outline.
        # Isolate the bright white core of the numbers.
        gray = cv2.cvtColor(search_area, cv2.COLOR_BGR2GRAY)
        # Threshold for very bright pixels
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        # Invert so text is black on white background
        processed_img = cv2.bitwise_not(thresh)
        
        cv2.imwrite(f"debug_ocr_crop_{offset_y}_processed.png", processed_img)
            
        results = self._reader.readtext(processed_img, allowlist=allowlist, mag_ratio=2.0)
        
        parsed_results = []
        for bbox, text, conf in results:
            # bbox is a list of 4 points [top_left, top_right, bottom_right, bottom_left]
            x_coords = [pt[0] for pt in bbox]
            y_coords = [pt[1] for pt in bbox]
            x = int(min(x_coords)) + offset_x
            y = int(min(y_coords)) + offset_y
            w = int(max(x_coords) - min(x_coords))
            h = int(max(y_coords) - min(y_coords))
            
            parsed_results.append(OCRResult(
                text=text,
                confidence=conf,
                bbox=(x, y, w, h)
            ))
            
        return parsed_results

    def read_number(self, image: np.ndarray,
                    region: tuple[int, int, int, int] | None = None) -> int | None:
        """Read a number from the image, parsing K and M suffixes."""
        # Use allowlist to focus on numbers and common suffixes. Add space for CoC fonts!
        results = self.read_text(image, region, allowlist="0123456789KkMm., ")
        if not results:
            return None
            
        # Join all text and clean it
        text = " ".join([r.text for r in results]).strip().upper()
        
        # Extract multiplier based on suffix
        multiplier = 1
        if "K" in text:
            multiplier = 1_000
        elif "M" in text:
            multiplier = 1_000_000
            
        # Remove anything that isn't a digit or decimal point
        cleaned_num = re.sub(r"[^\d.]", "", text)
        if not cleaned_num:
            return None
            
        try:
            return int(float(cleaned_num) * multiplier)
        except ValueError:
            logger.debug(f"Failed to parse number from OCR text: '{text}'")
            return None

    def read_resource_bar(self, image: np.ndarray) -> dict[str, int | None]:
        """Read all resources from the top resource bar."""
        # This implementation requires specific regions which should be passed in or configured
        # Placeholder implementation
        logger.warning("read_resource_bar requires specific regions to be implemented correctly.")
        return {'gold': None, 'elixir': None, 'dark_elixir': None, 'gems': None}

    def read_loot_available(self, image: np.ndarray, regions: dict[str, dict] | None = None) -> dict[str, int | None]:
        """Read available loot on enemy base during search."""
        loot = {'gold': None, 'elixir': None, 'dark_elixir': None}
        if not regions:
            logger.warning("No regions provided for OCR loot reading.")
            return loot
            
        for resource in loot.keys():
            region_name = f"enemy_{resource}"
            if region_name in regions:
                r = regions[region_name]
                # Extract (x, y, w, h)
                bbox = (r.get('x', 0), r.get('y', 0), r.get('width', 0), r.get('height', 0))
                if all(v > 0 for v in bbox):
                    val = self.read_number(image, bbox)
                    loot[resource] = val
                    logger.debug(f"OCR {resource}: {val}")
                else:
                    logger.warning(f"Invalid bounding box for {region_name}: {r}")
            
        return loot
