"""
🐔 SmartFarm IoT Simulator
Simulates IoT sensor data being sent to the API continuously.

Usage:
    python iot_simulator.py

The script will:
1. Login to get JWT token
2. Find or create a kandang
3. POST sensor data every 30 seconds (simulating 30-minute intervals)
4. Occasionally simulate abnormal conditions (high temp/ammonia, deaths)

Press Ctrl+C to stop.
"""

import requests
import time
import random
import sys
from datetime import datetime, timezone, timedelta

# Configuration
API_URL = "http://localhost:8000"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
INTERVAL_SECONDS = 30  # Real interval between POSTs (30s = simulated 30min)

# Timezone WIB (UTC+7)
WIB = timezone(timedelta(hours=7))


def login() -> dict:
    """Login and get access token."""
    print("🔐 Logging in...")
    res = requests.post(f"{API_URL}/api/v1/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    if res.status_code != 200:
        print(f"❌ Login failed: {res.text}")
        sys.exit(1)
    
    data = res.json()
    token = data.get("data", {}).get("access_token") or data.get("access_token")
    if not token:
        print(f"❌ No access token in response: {data}")
        sys.exit(1)
    
    print(f"✅ Logged in as {ADMIN_USERNAME}")
    return {"Authorization": f"Bearer {token}"}


def get_or_create_kandang(headers: dict) -> str:
    """Get existing kandang or create one. Returns kandang_id."""
    # Try to get existing kandangs
    res = requests.get(f"{API_URL}/api/v1/kandangs", headers=headers)
    if res.status_code == 200:
        data = res.json()
        # Handle different response formats
        if isinstance(data, dict):
            items = data.get("data", {})
            if isinstance(items, dict):
                items = items.get("items", [])
            elif isinstance(items, list):
                pass  # items is already a list
            else:
                items = []
        elif isinstance(data, list):
            items = data
        else:
            items = []
        
        if items:
            kandang = items[0]
            print(f"📦 Using existing kandang: {kandang['nama']} ({kandang['id']})")
            return kandang["id"]
    
    # Get pemilik user ID (admin's own ID for simplicity)
    res = requests.get(f"{API_URL}/api/v1/auth/me", headers=headers)
    if res.status_code != 200:
        print(f"❌ Failed to get user info: {res.text}")
        sys.exit(1)
    
    user_data = res.json()
    user_id = user_data.get("data", {}).get("id") or user_data.get("id")
    
    # Need a pemilik user. Check if there's one
    res = requests.get(f"{API_URL}/api/v1/users?role=pemilik", headers=headers)
    pemilik_id = user_id  # fallback to admin
    if res.status_code == 200:
        users = res.json().get("data", {}).get("items", [])
        if users:
            pemilik_id = users[0]["id"]
    
    # Create kandang
    kandang_data = {
        "nama": "Kandang Utama",
        "kode": "KDG-01",
        "lokasi": "Blok A - Area Utama",
        "kapasitas": 10000,
        "deskripsi": "Kandang utama untuk monitoring IoT SmartFarm",
        "pemilik_id": pemilik_id,
    }
    
    res = requests.post(f"{API_URL}/api/v1/kandangs", headers=headers, json=kandang_data)
    if res.status_code in (200, 201):
        data = res.json()
        kandang_id = data.get("data", {}).get("id")
        print(f"📦 Created kandang: {kandang_data['nama']} ({kandang_id})")
        return kandang_id
    else:
        print(f"❌ Failed to create kandang: {res.text}")
        sys.exit(1)


def generate_sensor_data(hari_ke: int, simulasi_jam: int, is_abnormal: bool = False) -> dict:
    """
    Generate realistic sensor data.

    Normal conditions (Broiler chicken):
    - Temperature: 28-32°C
    - Humidity: 60-75%
    - Ammonia: 0-15 ppm
    - Death: 0-2 per interval
    
    Abnormal conditions:
    - Temperature: >34°C or <25°C
    - Humidity: >85% or <50%
    - Ammonia: >20 ppm
    - Death: 3-10 per interval
    """
    if is_abnormal:
        # Simulate abnormal conditions
        scenario = random.choice(["hot", "cold", "humid", "ammonia", "combined"])
        
        if scenario == "hot":
            suhu = round(random.uniform(34.0, 38.0), 1)
            kelembaban = round(random.uniform(55.0, 70.0), 1)
            amoniak = round(random.uniform(10.0, 20.0), 1)
            death = random.randint(2, 8)
        elif scenario == "cold":
            suhu = round(random.uniform(22.0, 25.0), 1)
            kelembaban = round(random.uniform(70.0, 85.0), 1)
            amoniak = round(random.uniform(5.0, 15.0), 1)
            death = random.randint(1, 5)
        elif scenario == "humid":
            suhu = round(random.uniform(29.0, 33.0), 1)
            kelembaban = round(random.uniform(85.0, 95.0), 1)
            amoniak = round(random.uniform(8.0, 18.0), 1)
            death = random.randint(1, 4)
        elif scenario == "ammonia":
            suhu = round(random.uniform(28.0, 32.0), 1)
            kelembaban = round(random.uniform(65.0, 75.0), 1)
            amoniak = round(random.uniform(20.0, 35.0), 1)
            death = random.randint(3, 10)
        else:  # combined
            suhu = round(random.uniform(35.0, 39.0), 1)
            kelembaban = round(random.uniform(85.0, 95.0), 1)
            amoniak = round(random.uniform(25.0, 40.0), 1)
            death = random.randint(5, 15)
        
        print(f"    ⚠️  ABNORMAL [{scenario}]: suhu={suhu}°C, hum={kelembaban}%, ammo={amoniak}ppm, death={death}")
    else:
        # Normal conditions
        suhu = round(random.uniform(28.0, 32.0), 1)
        kelembaban = round(random.uniform(60.0, 75.0), 1)
        amoniak = round(random.uniform(1.0, 12.0), 1)
        death = random.choices([0, 0, 0, 0, 1, 1, 2], weights=[40, 20, 15, 10, 8, 5, 2])[0]
    
    # Calculate other fields based on hari_ke
    base_bobot = 40 + (hari_ke * 45)  # ~45g per day growth
    bobot = round(base_bobot + random.uniform(-5, 5), 1)
    
    # Feed and water increase with age
    pakan = round((20 + hari_ke * 8) + random.uniform(-3, 3), 1)
    minum = round((40 + hari_ke * 12) + random.uniform(-5, 5), 1)
    
    return {
        "suhu": suhu,
        "kelembaban": kelembaban,
        "amoniak": amoniak,
        "pakan": max(10, pakan),
        "minum": max(20, minum),
        "bobot": max(30, bobot),
        "death": death,
    }


def post_sensor_data(headers: dict, kandang_id: str, hari_ke: int, 
                      populasi: int, simulasi_jam: int, is_abnormal: bool) -> dict:
    """Post sensor data to API."""
    sensor = generate_sensor_data(hari_ke, simulasi_jam, is_abnormal)
    
    now = datetime.now(WIB)
    
    payload = {
        "kandang_id": kandang_id,
        "timestamp": now.isoformat(),
        "hari_ke": hari_ke,
        "suhu": sensor["suhu"],
        "kelembaban": sensor["kelembaban"],
        "amoniak": sensor["amoniak"],
        "pakan": sensor["pakan"],
        "minum": sensor["minum"],
        "bobot": sensor["bobot"],
        "populasi": populasi,
        "death": sensor["death"],
    }
    
    res = requests.post(f"{API_URL}/api/v1/sensor-data", headers=headers, json=payload)
    
    if res.status_code in (200, 201):
        data = res.json()
        return {"success": True, "death": sensor["death"], "data": data}
    else:
        return {"success": False, "error": res.text, "death": 0}


def run_predictions(headers: dict, kandang_id: str, sensor_history: list):
    """Run ML predictions (classification + forecasting) using recent sensor data."""
    
    # --- Classification ---
    latest = sensor_history[-1] if sensor_history else None
    if latest:
        classify_payload = {
            "hari_ke": latest["hari_ke"],
            "suhu": latest["suhu"],
            "kelembaban": latest["kelembaban"],
            "amoniak": latest["amoniak"],
            "pakan": latest.get("pakan", 100),
            "minum": latest.get("minum", 200),
            "bobot": latest.get("bobot", 500),
            "populasi": latest.get("populasi", 5000),
            "luas_kandang": 120,
            "hour": datetime.now().hour,
            "kandang_id": kandang_id,
        }
        
        res = requests.post(f"{API_URL}/api/v1/predictions/classify", 
                          headers=headers, json=classify_payload)
        if res.status_code == 200:
            result = res.json().get("data", {})
            cls = result.get("classification", "?")
            conf = result.get("confidence", 0)
            emoji = "🟢" if cls == "Normal" else "🔴"
            print(f"    {emoji} Klasifikasi: {cls} ({conf:.1%})")
        else:
            print(f"    ⚠️  Classification failed: {res.status_code}")
    
    # --- Forecasting (need at least 4 data points) ---
    if len(sensor_history) >= 4:
        forecast_payload = {
            "sensor_history": [
                {
                    "temp": h["suhu"],
                    "hum": h["kelembaban"],
                    "ammo": h["amoniak"],
                    "Death": h["death"],
                }
                for h in sensor_history[-4:]
            ],
            "kandang_id": kandang_id,
        }
        
        res = requests.post(f"{API_URL}/api/v1/predictions/forecast", 
                          headers=headers, json=forecast_payload)
        if res.status_code == 200:
            result = res.json().get("data", {})
            pred_death = result.get("predicted_death", 0)
            has_risk = result.get("has_risk", False)
            emoji = "🔴" if has_risk else "🟢"
            print(f"    {emoji} Forecast: {pred_death} kematian diprediksi {'⚠️ RISIKO!' if has_risk else '(aman)'}")
        else:
            print(f"    ⚠️  Forecasting failed: {res.status_code}")
    else:
        remaining = 4 - len(sensor_history)
        print(f"    ⏳ Forecasting: butuh {remaining} data lagi...")


def main():
    print("=" * 60)
    print("🐔 SmartFarm IoT Simulator")
    print("=" * 60)
    print(f"📡 API: {API_URL}")
    print(f"⏱️  Interval: {INTERVAL_SECONDS}s per reading")
    print(f"🎯 Abnormal rate: ~20% of readings")
    print("=" * 60)
    print()
    
    # Login
    headers = login()
    
    # Get or create kandang
    kandang_id = get_or_create_kandang(headers)
    
    # Simulation state
    hari_ke = 1
    populasi = 10000
    reading_count = 0
    sensor_history = []  # Keep last 10 readings for forecasting
    
    print()
    print(f"🚀 Starting IoT simulation (Ctrl+C to stop)")
    print(f"   Hari ke-{hari_ke}, Populasi awal: {populasi}")
    print("-" * 60)
    
    try:
        while True:
            reading_count += 1
            simulasi_jam = (reading_count * 30) // 60  # Simulated hours
            
            # Every 48 readings (~24 simulated hours), advance to next day
            if reading_count > 1 and reading_count % 48 == 0:
                hari_ke += 1
                print(f"\n📅 === HARI KE-{hari_ke} === (Populasi: {populasi})")
            
            # ~20% chance of abnormal
            is_abnormal = random.random() < 0.20
            
            timestamp = datetime.now(WIB).strftime("%H:%M:%S")
            print(f"\n[{timestamp}] Reading #{reading_count} (Hari {hari_ke})")
            
            # Post data
            result = post_sensor_data(headers, kandang_id, hari_ke, populasi, simulasi_jam, is_abnormal)
            
            if result["success"]:
                # Update populasi
                populasi -= result["death"]
                
                # Track history for forecasting
                sensor_reading = {
                    "hari_ke": hari_ke,
                    "suhu": result["data"]["data"]["suhu"] if "data" in result["data"] else 0,
                    "kelembaban": result["data"]["data"]["kelembaban"] if "data" in result["data"] else 0,
                    "amoniak": result["data"]["data"]["amoniak"] if "data" in result["data"] else 0,
                    "pakan": result["data"]["data"].get("pakan", 100) if "data" in result["data"] else 100,
                    "minum": result["data"]["data"].get("minum", 200) if "data" in result["data"] else 200,
                    "bobot": result["data"]["data"].get("bobot", 500) if "data" in result["data"] else 500,
                    "populasi": populasi,
                    "death": result["death"],
                }
                sensor_history.append(sensor_reading)
                sensor_history = sensor_history[-10:]  # Keep last 10
                
                print(f"    ✅ Data posted (death: {result['death']}, pop: {populasi})")
                
                # Run ML predictions automatically
                run_predictions(headers, kandang_id, sensor_history)
            else:
                print(f"    ❌ Failed: {result['error'][:100]}")
            
            # Wait
            print(f"    ⏳ Next reading in {INTERVAL_SECONDS}s...")
            time.sleep(INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\n")
        print("=" * 60)
        print("🛑 Simulator stopped")
        print(f"   Total readings: {reading_count}")
        print(f"   Final day: {hari_ke}")
        print(f"   Final population: {populasi}")
        print("=" * 60)


if __name__ == "__main__":
    main()
