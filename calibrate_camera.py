# calibrate_camera.py — Updated to only save valid chessboard images (KRTLUK002)

import cv2
import numpy as np
import os
import sys
import time
from picamera2 import Picamera2
from libcamera import Transform
import glob

def collect_calibration_points(image_glob, board_size, square_size, criteria):
    objp = np.zeros((board_size[0]*board_size[1], 3), np.float32)
    objp[:, :2] = np.indices(board_size).T.reshape(-1, 2) * square_size

    objpoints = []
    imgpoints = []

    images = glob.glob(image_glob)
    if not images:
        print(f"No images found with pattern: {image_glob}", file=sys.stderr)
        sys.exit(1)

    for fname in images:
        img = cv2.imread(fname)
        if img is None:
            print(f"Warning: failed to load {fname}", file=sys.stderr)
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        flags = cv2.CALIB_CB_FAST_CHECK | cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
        found, corners = cv2.findChessboardCornersSB(gray, board_size, flags)

        if not found:
            print(f"Chessboard not found in {fname}")
            continue

        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        objpoints.append(objp)
        imgpoints.append(corners)

        cv2.drawChessboardCorners(img, board_size, corners, found)
        cv2.imshow('Corners', img)
        cv2.waitKey(100)

    cv2.destroyAllWindows()
    return objpoints, imgpoints, gray.shape[::-1]

def calibrate_camera(objpoints, imgpoints, image_size):
    if not objpoints:
        raise RuntimeError("No corners were detected in any image.")
    rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, image_size, None, None)
    return rms, K, dist, rvecs, tvecs

def compute_reprojection_error(objpoints, imgpoints, rvecs, tvecs, K, dist):
    total_error = 0
    for objp, imgp, rvec, tvec in zip(objpoints, imgpoints, rvecs, tvecs):
        proj, _ = cv2.projectPoints(objp, rvec, tvec, K, dist)
        total_error += cv2.norm(imgp, proj, cv2.NORM_L2) / len(proj)
    return total_error / len(objpoints)

def capture_checkerboard_images(num_images, board_size, save_dir):
    print(f"Capturing {num_images} valid chessboard images using PiCamera...")
    os.makedirs(save_dir, exist_ok=True)

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)})
    picam2.configure(config)
    picam2.start()
    time.sleep(2)

    count = 0
    while count < num_images:
        frame = picam2.capture_array()
        display = frame.copy()
        cv2.putText(display, f"Press 's' to snap ({count}/{num_images})", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.imshow("Live Preview", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            found, corners = cv2.findChessboardCornersSB(gray, board_size)
            if found:
                filename = os.path.join(save_dir, f"chessboard_{count:02d}.jpg")
                cv2.imwrite(filename, frame)
                print(f"[SAVED] {filename}")
                count += 1
            else:
                print("[SKIPPED] Chessboard not found — try again.")
        elif key == ord('q'):
            print("Capture aborted.")
            break

    picam2.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    board_size = (4, 4)       # For a 5×5 squares checkerboard
    square_size = 19.0        # mm
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    save_dir = "/home/lukea/hailo-rpi5-examples/basic_pipelines/checkerboard_images"

    try:
        num_images = int(input("How many valid images should be captured? "))
    except ValueError:
        print("Invalid input.")
        sys.exit(1)

    capture_checkerboard_images(num_images, board_size, save_dir)

    objpoints, imgpoints, img_size = collect_calibration_points(f"{save_dir}/*.jpg", board_size, square_size, criteria)

    print(f"[DEBUG] Number of valid detections: {len(objpoints)}")
    rms, K, dist, rvecs, tvecs = calibrate_camera(objpoints, imgpoints, img_size)
    print(f"RMS reprojection error: {rms:.4f}")
    print("Camera matrix:\n", K)
    print("Distortion coefficients:\n", dist.ravel())

    mean_error = compute_reprojection_error(objpoints, imgpoints, rvecs, tvecs, K, dist)
    print(f"Mean reprojection error (per image): {mean_error:.4f} px")

    np.savez("/home/lukea/hailo-rpi5-examples/basic_pipelines/new_camera_calibration.npz", K=K, dist=dist)
    print("Calibration saved to new_camera_calibration.npz")
