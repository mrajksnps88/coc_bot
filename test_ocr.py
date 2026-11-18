import cv2
import easyocr
import numpy as np
import sys

def preprocess_image(img_path):
    img = cv2.imread(img_path)
    if img is None:
        print(f"Failed to load {img_path}")
        return None
        
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # The text in CoC is typically white/light with a heavy black outline.
    # We want to isolate the white core.
    # Let's threshold for very bright pixels (e.g., > 200)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    
    # EasyOCR prefers black text on white background
    inverted = cv2.bitwise_not(thresh)
    
    # Save the preprocessed image to see what it looks like
    cv2.imwrite(f"preprocessed_{img_path}", inverted)
    return inverted

def main():
    reader = easyocr.Reader(['en'])
    images = ["debug_ocr_crop_119.png", "debug_ocr_crop_169.png", "debug_ocr_crop_217.png"]
    
    for img_path in images:
        print(f"\nProcessing {img_path}...")
        
        # Test 1: Raw image
        results_raw = reader.readtext(img_path, allowlist="0123456789 ", mag_ratio=2.0)
        print("Raw results:", results_raw)
        
        # Test 2: Preprocessed image
        processed_img = preprocess_image(img_path)
        if processed_img is not None:
            results_proc = reader.readtext(processed_img, allowlist="0123456789 ", mag_ratio=2.0)
            print("Preprocessed results:", results_proc)

if __name__ == "__main__":
    main()
