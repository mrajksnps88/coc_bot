"""Region Selector Tool
Usage: python -m coc_bot.tools.region_selector

Captures a screenshot, lets you click to define named regions.
"""

import cv2
import sys
import numpy as np
from pathlib import Path

from coc_bot.utils.adb_utils import ADBConnection
from coc_bot.modules.capture.adb_capture import ADBCapture
from coc_bot.config.settings import ADBSettings

polygon_pts = []
img = None
clone = None

def draw_polygon(event, x, y, flags, param):
    global polygon_pts, img, clone
    
    if event == cv2.EVENT_LBUTTONDOWN:
        polygon_pts.append((x, y))
        # Draw on the original image so it persists
        if len(polygon_pts) == 1:
            cv2.circle(img, (x, y), 3, (0, 255, 0), -1)
        elif len(polygon_pts) > 1:
            cv2.circle(img, (x, y), 3, (0, 255, 0), -1)
            cv2.line(img, polygon_pts[-2], polygon_pts[-1], (0, 255, 0), 2)
            
    elif event == cv2.EVENT_MOUSEMOVE:
        if len(polygon_pts) > 0:
            # Draw temporary line to mouse cursor
            img_copy = img.copy()
            cv2.line(img_copy, polygon_pts[-1], (x, y), (0, 255, 0), 1)
            cv2.imshow("Polygon Selector", img_copy)

def main():
    global img, clone, polygon_pts
    
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
    
    cv2.namedWindow("Polygon Selector")
    cv2.setMouseCallback("Polygon Selector", draw_polygon)
    
    print("\nControls:")
    print("  - Left Click to add a point to the polygon")
    print("  - Press 'c' to close polygon, save, and exit")
    print("  - Press 't' to save the last clicked dot as your Troop Slot coordinate")
    print("  - Press 'w' to save the last clicked dot as your Dedicated Wall Piece coordinate")
    print("  - Press 'u' to save the last clicked dot as the 'Upgrade with Gold' button")
    print("  - Press 'i' to save the last clicked dot as the 'Upgrade with Elixir' button")
    print("  - Press 'y' to save the last clicked dot as the final green 'Confirm' button")
    print("  - Press 'g' to draw OCR box for your Gold amount")
    print("  - Press 'e' to draw OCR box for your Elixir amount")
    print("  - Press 'j' to draw OCR box for Enemy Gold amount")
    print("  - Press 'k' to draw OCR box for Enemy Elixir amount")
    print("  - Press 'r' to reset polygon")
    print("  - Press 'n' to take new screenshot")
    print("  - Press 'q' to quit without saving\n")
    
    while True:
        # If there are no points, we just show the original image.
        # If there are points, MOUSEMOVE is handling the temp drawing on an img_copy.
        # To avoid flicker when mouse isn't moving, we just show the base `img` with the points drawn.
        if len(polygon_pts) == 0:
            cv2.imshow("Polygon Selector", img)
            
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord("r"):
            img = clone.copy()
            polygon_pts = []
            cv2.imshow("Polygon Selector", img)
            
        elif key == ord("n"):
            print("Grabbing new screenshot...")
            new_img = capturer.grab()
            if new_img is not None:
                img = new_img
                clone = img.copy()
                polygon_pts = []
                cv2.imshow("Polygon Selector", img)
            else:
                print("Failed to grab.")
                
        elif key == ord("t"):
            if len(polygon_pts) > 0:
                last_pt = polygon_pts.pop()
                # Redraw without the point
                img = clone.copy()
                for pt in polygon_pts:
                    cv2.circle(img, pt, 5, (0, 0, 255), -1)
                cv2.imshow("Polygon Selector", img)
                
                try:
                    from ruamel.yaml import YAML
                    yaml = YAML()
                    yaml.preserve_quotes = True
                    
                    config_path = Path("coc_bot/config/game_config.yaml")
                    if config_path.exists():
                        with open(config_path, "r") as f:
                            data = yaml.load(f)
                        
                        if 'farming' not in data:
                            data['farming'] = {}
                            
                        # Legacy compatibility
                        data['farming']['troop_slot_x'] = last_pt[0]
                        data['farming']['troop_slot_y'] = last_pt[1]
                        
                        # Append to new list
                        if 'troop_slots' not in data['farming'] or not isinstance(data['farming']['troop_slots'], list):
                            data['farming']['troop_slots'] = []
                        data['farming']['troop_slots'].append([last_pt[0], last_pt[1]])
                        
                        with open(config_path, "w") as f:
                            yaml.dump(data, f)
                        print(f"\nSuccessfully appended troop slot at {last_pt} to {config_path}")
                        print(f"Current troop sequence length: {len(data['farming']['troop_slots'])}")
                    else:
                        print(f"\nConfig file not found at {config_path}")
                except Exception as e:
                    print(f"Failed to save to config file: {e}")
            else:
                print("Please click on a troop slot first!")
                
        elif key == ord("k"):
            try:
                from ruamel.yaml import YAML
                yaml = YAML()
                yaml.preserve_quotes = True
                
                config_path = Path("coc_bot/config/game_config.yaml")
                if config_path.exists():
                    with open(config_path, "r") as f:
                        data = yaml.load(f)
                    
                    if 'farming' in data and 'troop_slots' in data['farming']:
                        data['farming']['troop_slots'] = []
                        with open(config_path, "w") as f:
                            yaml.dump(data, f)
                        print("\nSuccessfully cleared troop slots sequence in config!")
                else:
                    print(f"\nConfig file not found at {config_path}")
            except Exception as e:
                print(f"Failed to clear config file: {e}")
                
        elif key == ord("w"):
            if len(polygon_pts) > 0:
                last_pt = polygon_pts.pop()
                # Redraw without the point
                img = clone.copy()
                for pt in polygon_pts:
                    cv2.circle(img, pt, 5, (0, 0, 255), -1)
                cv2.imshow("Polygon Selector", img)
                
                try:
                    from ruamel.yaml import YAML
                    yaml = YAML()
                    yaml.preserve_quotes = True
                    
                    config_path = Path("coc_bot/config/game_config.yaml")
                    if config_path.exists():
                        with open(config_path, "r") as f:
                            data = yaml.load(f)
                        
                        if 'auto_wall' not in data:
                            data['auto_wall'] = {}
                            
                        data['auto_wall']['wall_x'] = last_pt[0]
                        data['auto_wall']['wall_y'] = last_pt[1]
                        data['auto_wall']['enabled'] = True
                        
                        with open(config_path, "w") as f:
                            yaml.dump(data, f)
                        print(f"\nSuccessfully saved 'wall_x/y' at {last_pt} and enabled auto_wall to {config_path}")
                    else:
                        print(f"\nConfig file not found at {config_path}")
                except Exception as e:
                    print(f"Failed to save to config file: {e}")
            else:
                print("Please click on your dedicated wall piece first!")
                
        elif key in [ord("u"), ord("i"), ord("y"), ord("a"), ord("f"), ord("m")]:
            if len(polygon_pts) > 0:
                last_pt = polygon_pts.pop()
                img = clone.copy()
                for pt in polygon_pts:
                    cv2.circle(img, pt, 5, (0, 0, 255), -1)
                cv2.imshow("Polygon Selector", img)
                
                if key == ord("u"): name = "btn_gold"
                elif key == ord("i"): name = "btn_elixir"
                elif key == ord("y"): name = "btn_confirm"
                elif key == ord("a"): name = "attack_button"
                elif key == ord("f"): name = "find_match"
                elif key == ord("m"): name = "confirm_match"
                
                try:
                    from ruamel.yaml import YAML
                    yaml = YAML()
                    yaml.preserve_quotes = True
                    
                    config_path = Path("coc_bot/config/game_config.yaml")
                    if config_path.exists():
                        with open(config_path, "r") as f:
                            data = yaml.load(f)
                            
                        if name in ["attack_button", "find_match", "confirm_match"]:
                            if 'screen_regions' not in data:
                                data['screen_regions'] = {}
                            data['screen_regions'][name] = {
                                'x': last_pt[0] - 50,
                                'y': last_pt[1] - 50,
                                'width': 100,
                                'height': 100
                            }
                        else:
                            if 'auto_wall' not in data:
                                data['auto_wall'] = {}
                            data['auto_wall'][f'{name}_x'] = last_pt[0]
                            data['auto_wall'][f'{name}_y'] = last_pt[1]
                        
                        with open(config_path, "w") as f:
                            yaml.dump(data, f)
                        print(f"\nSuccessfully saved '{name}' at {last_pt} to {config_path}")
                    else:
                        print(f"\nConfig file not found at {config_path}")
                except Exception as e:
                    print(f"Failed to save to config file: {e}")
            else:
                print("Please click on the upgrade button first!")
                
        elif key in [ord("g"), ord("e"), ord("j"), ord("k")]:
            if key == ord("g"): name = "own_gold"
            elif key == ord("e"): name = "own_elixir"
            elif key == ord("j"): name = "enemy_gold"
            elif key == ord("k"): name = "enemy_elixir"
            
            print(f"\nSelecting OCR region for {name}...")
            print("Click and drag a box around the number, then press ENTER or SPACE to save.")
            roi = cv2.selectROI("Polygon Selector", img, fromCenter=False, showCrosshair=True)
            if roi[2] > 0 and roi[3] > 0:  # width and height > 0
                try:
                    from ruamel.yaml import YAML
                    yaml = YAML()
                    yaml.preserve_quotes = True
                    
                    config_path = Path("coc_bot/config/game_config.yaml")
                    if config_path.exists():
                        with open(config_path, "r") as f:
                            data = yaml.load(f)
                        
                        if 'screen_regions' not in data:
                            data['screen_regions'] = {}
                            
                        data['screen_regions'][name] = {
                            'x': int(roi[0]),
                            'y': int(roi[1]),
                            'width': int(roi[2]),
                            'height': int(roi[3])
                        }
                        
                        with open(config_path, "w") as f:
                            yaml.dump(data, f)
                        print(f"Successfully saved '{name}' region {roi} to {config_path}")
                    else:
                        print(f"Config file not found at {config_path}")
                except Exception as e:
                    print(f"Failed to save to config file: {e}")
            else:
                print("Selection cancelled.")
                
        elif key == ord("c"):
            if len(polygon_pts) >= 3:
                # Close the visual polygon
                cv2.line(img, polygon_pts[-1], polygon_pts[0], (0, 255, 0), 2)
                cv2.imshow("Polygon Selector", img)
                cv2.waitKey(500) # pause to let them see it closed
                
                try:
                    from ruamel.yaml import YAML
                    yaml = YAML()
                    yaml.preserve_quotes = True
                    
                    config_path = Path("coc_bot/config/game_config.yaml")
                    if config_path.exists():
                        with open(config_path, "r") as f:
                            data = yaml.load(f)
                        
                        if 'screen_regions' not in data:
                            data['screen_regions'] = {}
                            
                        # Format as list of lists [[x1,y1], [x2,y2]]
                        data['screen_regions']['deploy_polygon'] = [[p[0], p[1]] for p in polygon_pts]
                        
                        with open(config_path, "w") as f:
                            yaml.dump(data, f)
                        print(f"\nSuccessfully saved 'deploy_polygon' with {len(polygon_pts)} points to {config_path}")
                    else:
                        print(f"\nConfig file not found at {config_path}")
                except Exception as e:
                    print(f"Failed to save to config file: {e}")
                
                break
            else:
                print("Need at least 3 points to form a polygon.")
                
        elif key == ord("q"):
            break
            
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
