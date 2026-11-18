"""Template Capture Tool
Usage: python -m coc_bot.tools.template_capture

Captures a screenshot from ADB, displays it with OpenCV,
lets you draw rectangles to crop and save as templates.
"""

import cv2
import sys
import argparse
from pathlib import Path

from coc_bot.utils.adb_utils import ADBConnection
from coc_bot.modules.capture.adb_capture import ADBCapture
from coc_bot.config.settings import ADBSettings

drawing = False
ix, iy = -1, -1
fx, fy = -1, -1
img = None
clone = None

def draw_rect(event, x, y, flags, param):
    global ix, iy, fx, fy, drawing, img, clone
    
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
        
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            img_copy = clone.copy()
            cv2.rectangle(img_copy, (ix, iy), (x, y), (0, 255, 0), 2)
            cv2.imshow("Template Capture", img_copy)
            
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        fx, fy = x, y
        cv2.rectangle(img, (ix, iy), (fx, fy), (0, 255, 0), 2)
        cv2.imshow("Template Capture", img)

def main():
    global img, clone, ix, iy, fx, fy
    
    print("Connecting to ADB...")
    settings = ADBSettings()
    adb = ADBConnection(settings)
    try:
        adb.connect()
    except Exception as e:
        print(f"Failed to connect to ADB: {e}")
        sys.exit(1)
        
    if not adb.is_connected():
        print("Failed to connect to ADB.")
        sys.exit(1)
        
    capturer = ADBCapture(settings, adb)
    
    print("Grabbing screenshot...")
    img = capturer.grab()
    if img is None:
        print("Failed to grab screenshot.")
        sys.exit(1)
        
    clone = img.copy()
    
    cv2.namedWindow("Template Capture")
    cv2.setMouseCallback("Template Capture", draw_rect)
    
    print("\nControls:")
    print("  - Click and drag to select region")
    print("  - Press 's' to save selection as template")
    print("  - Press 'r' to reset selection")
    print("  - Press 'n' to take new screenshot")
    print("  - Press 'q' to quit\n")
    
    while True:
        cv2.imshow("Template Capture", img)
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord("r"):
            img = clone.copy()
            ix, iy, fx, fy = -1, -1, -1, -1
            
        elif key == ord("n"):
            print("Grabbing new screenshot...")
            img = capturer.grab()
            if img is not None:
                clone = img.copy()
            else:
                print("Failed to grab.")
                
        elif key == ord("s"):
            if ix != -1 and iy != -1 and fx != -1 and fy != -1:
                # Ensure correct coordinates
                x1, x2 = min(ix, fx), max(ix, fx)
                y1, y2 = min(iy, fy), max(iy, fy)
                
                if x2 - x1 > 0 and y2 - y1 > 0:
                    roi = clone[y1:y2, x1:x2]
                    
                    name = input("Enter template name (e.g. common/home_button): ")
                    if name:
                        path = Path(f"templates/{name}.png")
                        path.parent.mkdir(parents=True, exist_ok=True)
                        cv2.imwrite(str(path), roi)
                        print(f"Saved {path}")
                        
                        img = clone.copy()
                        ix, iy, fx, fy = -1, -1, -1, -1
                else:
                    print("Invalid region selected.")
            else:
                print("No region selected.")
                
        elif key == ord("q"):
            break
            
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
