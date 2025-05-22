import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import os
import numpy as np
import cv2
import hailo
import time
from picamera2 import Picamera2
from libcamera import Transform
from log_gps_info import get_gps_coordinates
import datetime
from math import radians, cos, sin, sqrt, atan2
import csv
import subprocess
import base64
from io import BytesIO
from PIL import Image

from hailo_apps_infra.hailo_rpi_common import (
    get_caps_from_pad,
    get_numpy_from_buffer,
    app_callback_class,
)
from hailo_apps_infra.detection_pipeline import GStreamerDetectionApp

# -----------------------------------
# Calibration data for size estimation
# -----------------------------------
def check_or_run_calibration():
    if not os.path.exists("/home/lukea/hailo-rpi5-examples/basic_pipelines/new_camera_calibration.npz"):
        print("No calibration file found. Starting compulsory calibration...")
        subprocess.run(["python3", "basic_pipelines/calibrate.py"])
    else:
        choice = input("Calibration file found. Do you want to recalibrate? (yes/no): ").strip().lower()
        if choice == "yes":
            subprocess.run(["python3", "basic_pipelines/calibrate.py"])
        else:
            print("Using existing calibration.")

check_or_run_calibration()

calibrated_data = np.load('/home/lukea/hailo-rpi5-examples/basic_pipelines/new_camera_calibration.npz')
K = calibrated_data['K']
dist = calibrated_data['dist']
mm_per_pixel = calibrated_data['mm_per_pixel']
ref_pixel_width = calibrated_data['ref_pixel_width']
# -----------------------------------
# User-defined callback class
# -----------------------------------
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.new_variable = 42

    def new_function(self):
        return "The meaning of life is:"

# set up csv and tracking
log_file = open("pothole_log.csv", "a", newline="")
csv_writer = csv.writer(log_file)

if log_file.tell() == 0:
    csv_writer.writerow(["timestamp", "latitude", "longitude", "altitude", "area_m2", "confidence", "frame", "image_base64"])

last_pothole = {"lat": None, "lon": None, "time": None}

# ---- crop and encode pothole image ---- #
def crop_and_encode(frame, x_min, y_min, w, h):
    crop = frame[y_min:y_min+h, x_min:x_min+w]

    pil_image = Image.fromarray(crop)
    buffered = BytesIO()
    pil_image.save(buffered, format="JPEG")

    encoded_string = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    return encoded_string

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)
    a = sin(d_phi/2)**2 + cos(phi1)*cos(phi2)*sin(d_lambda/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))
# -----------------------------------
# Callback function for inference
# -----------------------------------
def app_callback(pad, info, user_data):
    global K, dist, mm_per_pixel
    print(">> Callback triggered")
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    user_data.increment()
    string_to_print = f"Frame count: {user_data.get_count()}\n"

    format, width, height = get_caps_from_pad(pad)
    print(f"[DEBUG] Pad caps — Format: {format}, Width: {width}, Height: {height}")
    frame = None
    if user_data.use_frame and format and width and height:
        raw_frame = get_numpy_from_buffer(buffer, format, width, height)
        if raw_frame is not None:
            try:
                frame = cv2.undistort(raw_frame, K, dist)
                if frame is None:
                    print("[WARNING] cv2.undistort returned None — using raw frame.")
                    frame = raw_frame
                else:
                    print("[DEBUG] Frame undistorted successfully.")
            except Exception as e:
                print(f"[ERROR] cv2.undistort failed: {e}")
                frame = raw_frame
        else:
            print("[ERROR] get_numpy_from_buffer() returned None.")
    else:
        print("[DEBUG] Frame not extracted: missing format, size, or use_frame=False.")


    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    detection_count = 0
    for detection in detections:
        label = "pothole"
        confidence = detection.get_confidence()

        # Track ID
        track_id = 0
        track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
        if len(track) == 1:
            track_id = track[0].get_id()
            
        bbox = detection.get_bbox()  # [x, y, width, height]

        # --- Size Estimation ---
        try:
            x_min = int(round(bbox.xmin()))
            y_min = int(round(bbox.ymin()))
            x_max = int(round(bbox.xmax()))
            y_max = int(round(bbox.ymax()))
        except Exception as e:
            continue
        
        # Compute the actual height and width
        w = x_max - x_min
        h = y_max - y_min
        
        if w <= 0 or h <= 0:
            continue  # Skip to next detection
        
        # Apply dynamic mm_per_pixel scaling
        Z_ratio = ref_pixel_width / w
        mm_per_pixel_dyn = mm_per_pixel * Z_ratio
        
        # Compute real-world dimensions
        real_w_m = w * mm_per_pixel_dyn / 1000
        real_h_m = h * mm_per_pixel_dyn / 1000
        area_m2 = (real_w_m * real_h_m)
        print(area_m2)
        
        accuracy = (1 - abs(area_m2 - ref_area) / ref_area) * 100
        accuracy = max(0, min(accuracy, 100))

        # --- Print info ---
        string_to_print += (
            f"Detection: ID: {track_id} Label: pothole Confidence: {confidence:.2f} "
            f"Area: {area_m2:.10f} m2"
        )
        detection_count += 1

        lat, lon, alt = get_gps_coordinates()
        frame_id = user_data.get_count()

        if lat is not None and lon is not None:
            should_log = False
            if last_pothole["lat"] is None:
                should_log = True
            else:
                dist = haversine(lat, lon, last_pothole["lat"], last_pothole["lon"])
                if dist > 5:
                    should_log = True

            if should_log:
                timestamp = datetime.datetime.now().isoformat()
                if frame is not None:
                    encoded_crop = crop_and_encode(frame, x_min, y_min, w, h)
                    print(f"[DEBUG] base64 image size: {len(encoded_crop)} characters")
                else:
                    encoded_crop = "" # Placeholder in case something goes wrong
                    print("[DEBUG] Skipped encoding — frame is None")
                csv_writer.writerow([timestamp, lat, lon, alt, area_m2, confidence, frame_id, encoded_crop])
                log_file.flush()
                print(f"[LOGGED] Pothole @ ({lat:.6f}, {lon:.6f}) | area={area_m2:.4f} m2 | conf={confidence:.2f}")
                last_pothole["lat"] = lat
                last_pothole["lon"] = lon
                last_pothole["time"] = timestamp
            else:
                print(f"[SKIPPED] Duplicate pothole @ ({lat:.6f}, {lon:.6f})")
        else:
            print("[WARNING] No GPS fix available")
        
        # --- Draw annotations ---
        if user_data.use_frame and frame is not None:
            cv2.rectangle(frame, (x_min, y_min), (x_min + w, y_min + h), (0, 255, 0), 2)
            cv2.putText(frame, f"pothole {confidence:.2f}", (x_min, y_min - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(frame, f"Area: {area_m2:.4f} m2", (x_min, y_min + h + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    if user_data.use_frame and frame is not None:
        cv2.putText(frame, f"Detections: {detection_count}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"{user_data.new_function()} {user_data.new_variable}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        user_data.set_frame(frame)
        
    print(string_to_print)
    return Gst.PadProbeReturn.OK

# -----------------------------------
# Main execution
# -----------------------------------
if __name__ == "__main__":
    user_data = user_app_callback_class()

    # Ensure camera warms up to prevent pipeline stalls
    try:
        picam2 = Picamera2()
        config = picam2.create_preview_configuration(main={"format": 'RGB888', "size" : (640, 480)})
        picam2.configure(config)
        picam2.start()
        time.sleep(2)
        picam2.stop()
        picam2.close()
        print("Camera pre-warm successful.")
    except Exception as e:
        print(f"Camera warm-up failed: {e}")
    
    # Handling GStreamer Errors during exit
    try:
        app = GStreamerDetectionApp(app_callback, user_data)
        user_data.use_frame = True
        app.run()
    except KeyboardInterrupt:
        print("Video stream shutting down")
    finally:
        if 'app' in locals():
            app.pipeline.set_state(Gst.State.NULL)
            del app
            print("GStreamer closed")
