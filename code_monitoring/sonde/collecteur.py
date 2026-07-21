import os
import sqlite3
import requests
import time

# --- CONFIGURATION ---
PARC_INFORMATIQUE = [
    "linux-srv-1", "linux-srv-2", 
    "win-wkst-1", "win-wkst-2", 
    "win-srv-indispensable"
]
DB_PATH = "/app/data/monitoring.db"
MAX_LIGNES = 2000 

def clean_name(name):
    """Supprime les tirets et colle tout (ex: linux-srv-1 -> linuxsrv1)"""
    return name.replace("-", "").replace("_", "")

def initialiser_db():
    dossier = os.path.dirname(DB_PATH)
    if not os.path.exists(dossier):
        os.makedirs(dossier)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for machine in PARC_INFORMATIQUE:
            table_name = clean_name(machine)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
                    os TEXT,
                    cpu_usage REAL,
                    gpu_usage REAL,
                    ram_usage REAL,
                    disk_usage REAL,
                    temp REAL,
                    users_count INTEGER
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS security_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
                    machine_name TEXT,
                    username TEXT,
                    event_type TEXT,
                    severity TEXT,
                    details TEXT
                )
            """)
        
        conn.commit()
        conn.close()
        print(" Base initialisée : Une table collée par asset.")
    except sqlite3.OperationalError as e:
        print(f" Erreur Initialisation : {e}")

def nettoyer_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for machine in PARC_INFORMATIQUE:
            table_name = clean_name(machine)
            cursor.execute(f"""
                DELETE FROM {table_name} 
                WHERE id NOT IN (
                    SELECT id FROM {table_name} 
                    ORDER BY timestamp DESC 
                    LIMIT {MAX_LIGNES}
                )
            """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur Nettoyage : {e}")

def collecter_donnees():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for machine in PARC_INFORMATIQUE:
        try:
            response = requests.get(f"http://{machine}:5000/stats", timeout=3)
            if response.status_code == 200:
                data = response.json()
                table_name = clean_name(machine)
                
                # Insertion propre dans la table dédiée
                cursor.execute(f"""
                    INSERT INTO {table_name} (
                        os, cpu_usage, gpu_usage, 
                        ram_usage, disk_usage, temp, users_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get('os', 'Unknown'),
                    data['cpu'],
                    data.get('gpu', 0.0),
                    data['ram'],
                    data.get('disk', 0.0),
                    data['temp'],
                    data['users']
                ))
                print(f" {machine} -> Table {table_name} : OK")
        except Exception:
            print(f"⚠{machine} injoignable.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialiser_db()
    while True:
        collecter_donnees()
        nettoyer_db()
        time.sleep(5)