# log_gps_info.py

import serial
import time
import csv
import glob
from datetime import datetime

# Converts NMEA coordinates to decimal degrees
def nmea_to_decimal(coord, direction):
    if not coord or coord == '':
        return None
    if direction in ['N', 'S']:
        degrees = int(coord[:2])
        minutes = float(coord[2:])
    else:
        degrees = int(coord[:3])
        minutes = float(coord[3:])
    decimal = degrees + minutes / 60
    if direction in ['S', 'W']:
        decimal *= -1
    return decimal

def find_port():
    for port in glob.glob("/dev/ttyUSB*"):
        try:
            ser = serial.Serial(port, baudrate=115200, timeout=1)
            ser.write(b'AT\r')
            time.sleep(1)
            ser.flushInput()
            ser.write(b'AT+CGPSINFO\r')
            time.sleep(1)
            response = ser.read(ser.in_waiting).decode(errors='ignore')
            ser.close()
            if "+CGPSINFO:" in response or "OK" in response:
                print(f"Found GPS on port {port}")
                return port
        except Exception as e:
            print(f"port {port} not ready: {e}")
            continue
    raise RuntimeError("No port found for GPS")

port = find_port()
ser = serial.Serial(port, baudrate=115200, timeout=1)
time.sleep(2)

def get_gps_coordinates():
    try:
        ser.write(b'AT+CGPS=1,1\r')
        ser.write(b'AT+CGPSINFO\r')
        time.sleep(1)
        response = ser.readlines()
        
        for line in response:
            if b'+CGPSINFO: ' in line:
                parts = line.decode().strip().split(":")[1].split(",")
                if len(parts) >= 7 and parts[0] != '':
                    lat = nmea_to_decimal(parts[0], parts[1])
                    lon = nmea_to_decimal(parts[2], parts[3])
                    alt = parts[6]
                    return lat, lon, alt

    except Exception as e:
        print(f"[GPS ERROR] {e}")
    return None, None, None

# This only runs if script is executed directly
if __name__ == '__main__':
    # Open CSV log file
    with open('gps_log.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'Latitude', 'Longitude', 'Altitude (m)'])

        print("Reading GPS coordinates... (Ctrl+C to stop)")
        try:
            while True:
                lat, lon, alt = get_gps_coordinates()
                if lat and lon:
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"[{now}] Latitude: {lat:.6f}, Longitude: {lon:.6f}, Altitude: {alt} m")
                    writer.writerow([now, lat, lon, alt])
                else:
                    print("No fix.")
                time.sleep(3)
        except KeyboardInterrupt:
            print("Stopped.")
            ser.close()

            
