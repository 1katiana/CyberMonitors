# -*- coding: utf-8 -*-
import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = "/app/data/monitoring.db"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def check_all_assets(parc):
    config = load_config()
    all_crises = []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for asset_name in parc:
        table_name = asset_name.replace("-", "").replace("_", "")
        try:
            cursor.execute(f"SELECT cpu_usage, ram_usage, disk_usage, temp, users_count, timestamp FROM {table_name} ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            
            if not row: continue

            # Données actuelles
            data = {
                "name": asset_name,
                "cpu": float(row[0]),
                "ram": float(row[1]),
                "disk": float(row[2]),
                "temp": float(row[3]),
                "users": int(row[4]),
                "time": row[5]
            }

            # Logique de détection
            asset_crises = []
            if data["cpu"] > config["cpu_threshold"]: asset_crises.append(f"CPU critique: {data['cpu']}%")
            if data["ram"] > config["ram_threshold"]: asset_crises.append(f"RAM saturée: {data['ram']}%")
            if data["disk"] > config["disk_threshold"]: asset_crises.append(f"Disque saturé : {data['disk']}%")
            if data["temp"] > config["temp_threshold"]: asset_crises.append(f"Surchauffe: {data['temp']}°C")
            if data["users"] > config["user_threshold"]: asset_crises.append(f"DDoS suspect: {data['users']} users")

            # Check si le serveur répond encore
            last_seen = datetime.strptime(data["time"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - last_seen > timedelta(minutes=config["max_delay_minutes"]):
                asset_crises.append(f"HORS-LIGNE depuis {data['time']}")

            if asset_crises:
                all_crises.append({
                    "asset": asset_name,
                    "details": asset_crises,
                    "time": data["time"]
                })
        except Exception as e:
            print(f"Erreur check {asset_name}: {e}")

    conn.close()
    return all_crises