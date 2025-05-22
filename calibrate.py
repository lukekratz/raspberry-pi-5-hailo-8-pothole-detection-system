# calibrate.py - KRTLUK002
# This is the main calibration scrip that calls calibrate_camera.py and calibrate_distance.py sequentially

import os
import sys
import subprocess
import cv2
import time
import numpy as np
from picamera2 import Picamera2
from libcamera import Transform

base_dir = os.path.dirname(os.path.abspath(__file__))
calibration_file = os.path.join(base_dir, "new_camera_calibration.npz")
camera_script = os.path.join(base_dir, "calibrate_camera.py")
distance_script = os.path.join(base_dir, "calibrate_distance.py")

def prompt_user():
    print("Has your camera been calibrated? (yes/no)")
    choice = input(">> ").strip().lower()
    if choice == "yes":
        print("Would you like to recalibrate the camera? (yes/no)")
        confirm = input(">> ").strip().lower()
        return confirm == "yes"
    else:
        print("No existing calibration file found. Calibration is required.")
        return True

def run_calibration_scripts():
    print("Initialising camera calibration...")
    print("Running camera calibration...")
    subprocess.run(["python3", camera_script])

    print("Initialising distance calibration...")
    print("Running distance calibration...")
    subprocess.run(["python3", distance_script])

    print("Calibration complete — results stored in camera_calibration.npz")

if __name__ == "__main__":
    if prompt_user():
        run_calibration_scripts()

    else:
        print("Calibration skipped.")
