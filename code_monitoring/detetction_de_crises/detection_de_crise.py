#!/usr/bin/env python3
import sqlite3
import json
from datetime import datetime, timedelta

def load_config():
    with open("config.json") as f:
        return json.load(f)

def fetch_latest_data():
    conn = sqlite3.connect("monitoring.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ram_usage, disk_usage, cpu_usage, users_count, process_count, timestamp
        FROM system_data
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if not row:
        return []

    return [{
        "name": "serveur 1",
        "ram": float(row[0].replace('%', '').strip()),
        "disk": float(row[1].replace('%', '').strip()),
        "cpu": float(row[2].replace('%', '').strip()),
        "users": int(row[3]),
        "processes": int(row[4]),
        "last_seen": row[5]
    }]

def check_crisis(data, config):
    crises = []
    now = datetime.now()

    for server in data:
        if server["ram"] >= config["ram_threshold"]:
            crises.append(f"RAM saturée ({server['ram']}%) sur {server['name']}")
        if server["disk"] >= config["disk_threshold"]:
            crises.append(f"Disque saturé ({server['disk']}%) sur {server['name']}")
        if server["cpu"] >= config["cpu_threshold"]:
            crises.append(f"CPU saturé ({server['cpu']}%) sur {server['name']}")
        if server["users"] > config["user_threshold"]:
            crises.append(f"Trop d'utilisateurs connectés ({server['users']}) sur {server['name']}")
        if server["processes"] > config["process_threshold"]:
            crises.append(f"Trop de processus actifs ({server['processes']}) sur {server['name']}")

        last_seen = datetime.strptime(server["last_seen"], "%Y-%m-%d %H:%M:%S")
        if now - last_seen > timedelta(minutes=config["max_delay_minutes"]):
            crises.append(f"Plus de données depuis {config['max_delay_minutes']} minutes pour {server['name']}")

    return crises

if __name__ == "__main__":
    config = load_config()
    data = fetch_latest_data()
    crises = check_crisis(data, config)

    if crises:
        for c in crises:
            print(c)
    else:
        print("Aucune crise détectée.")
