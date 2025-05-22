from flask import Flask, render_template
import socket, csv, os

app = Flask(__name__)
CSV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "pothole_log.csv")
)

def has_internet(host="8.8.8.8", port=53, timeout=1):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except OSError:
        return False

@app.route('/')
def display():
    if not has_internet():
        return render_template('wifi_required.html'), 503

    try:
        records = []
        with open(CSV_PATH, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Only accept rows that have all expected fields and non-empty
                if all(field in row and row[field].strip() for field in ["latitude", "longitude", "area_m2"]):
                    records.append({
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"]),
                        "area": float(row["area_m2"]),
                        "image_base64": row.get("image_base64", "")  # blank if missing
                    })

        print("DEBUG RECORDS →", records[:2])  # show first two records only
        return render_template('display.html', records=records)
    except Exception as e:
        return f"<h2>Error reading pothole CSV file: {e}</h2>", 500
