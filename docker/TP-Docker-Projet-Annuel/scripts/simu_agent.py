import time
import os
import random
import sys
import threading
from flask import Flask, jsonify

# --- CONFIGURATION ET ETAT ---
machine = os.environ.get('MACHINE_NAME', 'Inconnu')
os_type = os.environ.get('OS_TYPE', 'Inconnu')

# On ajoute "users" dans le dictionnaire initial
stats = {
    "cpu": 10.0,
    "gpu": 5.0,
    "ram": 30.0,
    "disk": 15.0,
    "temp": 30.0,
    "users": 1  # <--- Ajouté
}

# Valeurs de "repos"
base_cpu, base_ram, base_disk = 10.0, 30.0, 15.0

def run_simulation_loop():
    global base_cpu, base_ram, base_disk
    print(f"[{machine}] ({os_type}) Simulation démarrée...", flush=True)

    while True:
        # 1. PICS ALÉATOIRES
        if random.randint(1, 50) == 1:
            stats["cpu"] = random.uniform(85.0, 100.0)
            stats["gpu"] = random.uniform(70.0, 100.0)
            print(f"[{machine}] ⚡ Pic CPU détecté...", flush=True)

        if random.randint(1, 70) == 1:
            stats["ram"] = random.uniform(85.0, 100.0)

        # 2. SIMULATION DES UTILISATEURS (Variation aléatoire)
        # On simule entre 1 et 10 utilisateurs connectés
        if random.randint(1, 10) == 1:
            stats["users"] = max(1, min(10, stats["users"] + random.choice([-1, 1])))

        # 3. FLUCTUATIONS ET INERTIE
        base_cpu = max(5.0, min(25.0, base_cpu + random.uniform(-2, 2)))
        stats["cpu"] += (base_cpu - stats["cpu"]) * 0.20
        stats["ram"] += (base_ram - stats["ram"]) * 0.10
        stats["disk"] += (base_disk - stats["disk"]) * 0.30

        # 4. THERMIQUE
        target_temp = 25.0 + (stats["cpu"] * 0.95) + (stats["gpu"] * 0.3)
        stats["temp"] += (target_temp - stats["temp"]) * 0.35 + random.uniform(-0.5, 0.5)

        # Log console mis à jour
        print(f"[{machine}] CPU:{stats['cpu']:02.0f}% | Users:{stats['users']} | Temp:{stats['temp']:.1f}°C", flush=True)

        time.sleep(2)

# --- API FLASK ---
app = Flask(__name__)

@app.route('/stats')
def stats_api():
    # On renvoie les données à jour avec la clé "users"
    return jsonify({
        "machine": machine,
        "os": os_type,
        "cpu": round(stats["cpu"], 2),
        "ram": round(stats["ram"], 2),
        "disk": round(stats["disk"], 2),
        "temp": round(stats["temp"], 2),
        "users": stats["users"]  # <--- CRITIQUE : Cette ligne manquait !
    })

if __name__ == "__main__":
    threading.Thread(target=run_simulation_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)