"""Color Calibration Tool - Shows what the bot sees for each color range."""
import subprocess
import sys
import io
import time

import cv2
import numpy as np
from PIL import Image

from coc_bot.config.settings import ADBSettings
from coc_bot.modules.vision.color_detector import ColorDetector, COC_COLORS

def grab_screenshot():
    """Grab a screenshot via ADB."""
    settings = ADBSettings()
    addr = settings.device_address
    
    subprocess.run(["adb", "disconnect", addr], capture_output=True, timeout=5)
    subprocess.run(["adb", "connect", addr], capture_output=True, timeout=5)
    time.sleep(2)
    
    result = subprocess.run(
        ["adb", "-s", addr, "exec-out", "screencap", "-p"],
        capture_output=True, timeout=15,
    )
    
    if result.returncode != 0 or len(result.stdout) < 100:
        print("Failed to grab screenshot!")
        sys.exit(1)
    
    image = Image.open(io.BytesIO(result.stdout))
    return np.array(image.convert("RGB"))[:, :, ::-1].copy()


def main():
    print("Grabbing screenshot...")
    frame = grab_screenshot()
    print(f"Screenshot size: {frame.shape[1]}x{frame.shape[0]}")
    
    detector = ColorDetector(min_area=50)
    
    # Show detection counts for each color
    print("\n" + "=" * 50)
    print("COLOR DETECTION RESULTS")
    print("=" * 50)
    
    for name, color_range in COC_COLORS.items():
        detections = detector.detect(frame, name)
        total_area = sum(d.area for d in detections)
        print(f"\n  {name}:")
        print(f"    HSV range: {color_range.lower} → {color_range.upper}")
        print(f"    Detections: {len(detections)}")
        print(f"    Total area: {total_area} px")
        if detections:
            top3 = sorted(detections, key=lambda d: d.area, reverse=True)[:3]
            for i, d in enumerate(top3):
                print(f"    #{i+1}: area={d.area}, center={d.center}")
    
    # Create visual debug images
    print("\nGenerating debug images...")
    
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    for name, color_range in COC_COLORS.items():
        lower = np.array(color_range.lower)
        upper = np.array(color_range.upper)
        mask = cv2.inRange(hsv, lower, upper)
        
        # Draw detections on a copy
        debug = frame.copy()
        detections = detector.detect(frame, name)
        for d in detections:
            cv2.rectangle(debug, (d.x, d.y), (d.x + d.width, d.y + d.height), (0, 255, 0), 2)
        
        # Save mask and detection overlay
        cv2.imwrite(f"debug_mask_{name}.png", mask)
        cv2.imwrite(f"debug_detect_{name}.png", debug)
    
    # Also save the raw screenshot
    cv2.imwrite("debug_screenshot.png", frame)
    
    print("\nSaved debug images:")
    print("  debug_screenshot.png     — Raw screenshot")
    for name in COC_COLORS:
        print(f"  debug_mask_{name}.png    — Binary mask (white = detected)")
        print(f"  debug_detect_{name}.png  — Green boxes around detections")
    
    print("\nOpen debug_mask_gold_glow.png and debug_mask_elixir_glow.png")
    print("to see what the bot 'sees' for each color range.")
    print("If gold_glow mask is mostly black, the HSV range needs tuning.")

if __name__ == "__main__":
    main()
