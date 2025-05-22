# raspberry-pi-5-hailo-8-pothole-detection-system
This is the official repository for the automatic pothole detection, classification and sizing system

# Pothole Detection System

This project uses machine vision and a YOLOv8 model accelerated by the Hailo-8 chip to detect, classify, and estimate the size of potholes in real time. The system runs on a Raspberry Pi 5 with the Hailo AI HAT+ and a Raspberry Pi AI Camera.

---

## 🚀 Quick Start

### Install Hailo Drivers & SDK on Raspberry Pi 5
Follow the official guide to install the Hailo AI Software Suite for Raspberry Pi:
👉 [Hailo-RPi5-Examples](https://github.com/hailo-ai/hailo-rpi5-examples)

### Clone the Hailo Example Repository
```bash
git clone https://github.com/hailo-ai/hailo-rpi5-examples.git
cd hailo-rpi5-examples

Clone this repository as shown below:

cd ~/hailo-rpi5-examples/basic_pipelines/
git clone https://github.com/YOUR_USERNAME/pothole-detection-system.git
cd pothole-detection-system

Run the detection pipeline with this command:
python3 pothole_detection.py --input rpi --hef-path ~/path-to-hef-file/Pothole-YOLOv8.hef

