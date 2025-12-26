# backend/import_csv_api.py
import csv
import sys
import requests
from datetime import datetime, timezone

API = "http://127.0.0.1:8000/api/requests"

def import_via_api(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            payload = {
                'id': row.get('id'),
                'supply_type': row.get('supply_type'),
                'quantity': int(row['quantity']) if row.get('quantity') else 1,
                'timestamp': row.get('timestamp') or datetime.now(timezone.utc).isoformat(),
                'expiry_date': row.get('expiry_date') or None,
                'distance_km': float(row['distance_km']) if row.get('distance_km') else None,
                'destination': row.get('destination') or None
            }
            r = requests.post(API, json=payload)
            print(r.status_code, r.text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_csv_api.py path/to/requests.csv")
        sys.exit(1)
    import_via_api(sys.argv[1])