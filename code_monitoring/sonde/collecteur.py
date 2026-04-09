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

def initialiser_db():
    # FORCE la création du dossier data s'il n'existe pas
    dossier = os.path.dirname(DB_PATH)
    if not os.path.exists(dossier):
        os.makedirs(dossier)
        print(f"📁 Dossier créé : {dossier}")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                machine TEXT,
                cpu_usage REAL,
                ram_usage REAL,
                temp REAL,
                users_count INTEGER
            )
        """)
        conn.commit()
        conn.close()
        print("🗄️ Base de données initialisée avec succès.")
    except sqlite3.OperationalError as e:
        print(f"❌ Erreur SQLite : {e}")
        # Si ça échoue encore, on essaie de créer le fichier dans le dossier courant pour tester
        print("Tentative de secours dans le dossier courant...")
        conn = sqlite3.connect("monitoring_secours.db")
        conn.close()

def collecter_donnees():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for machine in PARC_INFORMATIQUE:
        try:
            response = requests.get(f"http://{machine}:5000/stats", timeout=3)
            if response.status_code == 200:
                data = response.json()
                
               
                cursor.execute("""
                    INSERT INTO system_data (machine, cpu_usage, ram_usage, temp, users_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (machine, data['cpu'], data['ram'], data['temp'], data['users']))
                
                print(f"✅ {machine} : {data['users']} utilisateurs connectés.")
        except Exception as e:
            print(f"⚠️ {machine} injoignable.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialiser_db()
    while True:
        collecter_donnees()
        time.sleep(5)  # Pause de 5 secondes entre chaque tour de contrôle