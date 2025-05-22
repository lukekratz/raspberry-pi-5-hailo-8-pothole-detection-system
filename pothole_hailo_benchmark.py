import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import os
import numpy as np
import cv2
import hailo
import time
import psutil

from hailo_apps_infra.hailo_rpi_common import (
    get_caps_from_pad,
    get_numpy_from_buffer,
    app_callback_class,
)
from hailo_apps_infra.detection_pipeline import GStreamerDetectionApp

# -----------------------------------------------------------------------------------------------
# Callback class with benchmarking stats
# -----------------------------------------------------------------------------------------------
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.total_confidence = 0.0
        self.total_detections = 0
        self.total_time = 0.0
        self.cpu_usages = []
        self.mem_usages = []

    def log_stats(self, start_time, frame_confidences):
        self.total_time += time.time() - start_time
        self.cpu_usages.append(psutil.cpu_percent())
        self.mem_usages.append(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
        self.total_confidence += sum(frame_confidences)
        self.total_detections += len(frame_confidences)

    def report(self):
        avg_conf = self.total_confidence / self.total_detections if self.total_detections else 0
        avg_time = self.total_time / self.get_count() if self.get_count() else 0
        peak_cpu = max(self.cpu_usages)
        avg_cpu = sum(self.cpu_usages) / len(self.cpu_usages) if self.cpu_usages else 0
        peak_mem = max(self.mem_usages)
        avg_mem = sum(self.mem_usages) / len(self.mem_usages) if self.mem_usages else 0

        print("\n--- Benchmark Summary ---")
        print(f"Total frames: {self.get_count()}")
        print(f"Total detections: {self.total_detections}")
        print(f"Average confidence: {avg_conf:.3f}")
        print(f"Average inference time: {avg_time*1000:.2f} ms")
        print(f"Peak CPU usage: {peak_cpu:.2f}%")
        print(f"Average CPU usage: {avg_cpu:.2f}%")
        print(f"Peak Memory usage: {peak_mem:.2f} MB/s")
        print(f"Average memory usage: {avg_mem:.2f} MB/s")
        print("--------------------------")

# -----------------------------------------------------------------------------------------------
# Callback function
# -----------------------------------------------------------------------------------------------
def app_callback(pad, info, user_data):
    start_time = time.time()
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    user_data.increment()
    format, width, height = get_caps_from_pad(pad)
    frame = None
    if user_data.use_frame and format and width and height:
        frame = get_numpy_from_buffer(buffer, format, width, height)

    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    confidences = []
    for det in detections:
        conf = det.get_confidence()
        confidences.append(conf)

    user_data.log_stats(start_time, confidences)

    return Gst.PadProbeReturn.OK

# -----------------------------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------------------------
if __name__ == "__main__":
    user_data = user_app_callback_class()
    app = GStreamerDetectionApp(app_callback, user_data)
    try:
        app.run()
    finally:
        user_data.report()
