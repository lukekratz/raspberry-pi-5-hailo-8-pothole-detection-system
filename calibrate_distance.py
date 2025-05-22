# calibrate_distance.py - KRTLUK002

import cv2
import numpy as np
import math
import os
from picamera2 import Picamera2
from libcamera import Transform
import time

# Maximum display size
MAX_DISPLAY_W, MAX_DISPLAY_H = 800, 800

# Resolve relative paths
base_dir = os.path.dirname(os.path.abspath(__file__))
calibration_file = os.path.join(base_dir, "new_camera_calibration.npz")

# Will hold the four clicked points (in original-image coordinates)
orig_points = []

def click_event(event, x, y, flags, param):
    global orig_points, display_img, scale
    if event == cv2.EVENT_LBUTTONDOWN and len(orig_points) < 4:
        # map display coords → original-image coords
        orig_x = int(x / scale)
        orig_y = int(y / scale)
        orig_points.append((orig_x, orig_y))
        # Draw circle on the display image
        cv2.circle(display_img, (x, y), 5, (0, 255, 0), -1)
        cv2.imshow(window_name, display_img)

        # Once we have 4 points, calculate widths
        if len(orig_points) == 4:

            tl, tr, br, bl = orig_points
            top_w    = math.hypot(tr[0] - tl[0], tr[1] - tl[1])
            bottom_w = math.hypot(br[0] - bl[0], br[1] - bl[1])
            print(f"Top edge width:    {top_w:.2f} px")
            print(f"Bottom edge width: {bottom_w:.2f} px")
            avg_px_width = (top_w + bottom_w) / 2

            try:
                ref_real_world_width_mm = float(input("Enter the real-world width of your reference object in millimeters (e.g. 190 for A4): "))
            except ValueError:
                print("Invalid number. Exiting.")
                exit(1)

            mm_per_pixel = ref_real_world_width_mm / avg_px_width
            print(f"Average mm per pixel: {mm_per_pixel:.6f} mm/px")

            # Save to existing calibration file
            try:
                data = np.load(calibration_file)
                np.savez(calibration_file, 
                         K=data["K"], 
                         dist=data["dist"], 
                         mm_per_pixel=mm_per_pixel, 
                         ref_pixel_width=avg_px_width)
                print(f"Calibration updated in {calibration_file}")
            except Exception as e:
                print(f"[ERROR] Could not save mm_per_pixel: {e}")

            cv2.destroyAllWindows()

if __name__ == "__main__":
    print("Place reference object in view of the camera.")
    print("Press 'k' to capture the image when ready.")

    picam2 = Picamera2()
    config = picam2.create_still_configuration(transform=Transform(vflip=0, hflip=0))
    picam2.configure(config)
    picam2.start()
    time.sleep(2)

    img = None
    while True:
        preview = picam2.capture_array()
        display = preview.copy()
        cv2.putText(display, "Press 'k' to capture A4 image", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.imshow("Live Preview", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('k'):
            img = preview.copy()
            break
        elif key == ord('q'):
            print("Capture aborted.")
            exit(0)

    picam2.stop()
    cv2.destroyAllWindows()

    if img is None:
        print("No image captured.")
        exit(1)

    # Resize for display
    h, w = img.shape[:2]
    scale_w = MAX_DISPLAY_W / w
    scale_h = MAX_DISPLAY_H / h
    scale = min(scale_w, scale_h, 1.0)

    disp_w = int(w * scale)
    disp_h = int(h * scale)
    display_img = cv2.resize(img, (disp_w, disp_h), interpolation=cv2.INTER_AREA)

    window_name = "Click TL, TR, BR, BL"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    cv2.imshow(window_name, display_img)
    cv2.setMouseCallback(window_name, click_event)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
