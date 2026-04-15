import time
import os
import random
import threading
from flask import Flask, jsonify

# --- 1. CONFIGURATION DE BASE ---
machine = os.environ.get('MACHINE_NAME', 'Inconnu')
os_type = os.environ.get('OS_TYPE', 'Inconnu')

# --- 2. PROFILS MATERIELS (Le coeur du realisme) ---
def get_hardware_profile(name):
    if "SRV-WIN-CORE" in name:
        return {"ram_total_gb": 128.0, "disk_total_gb": 4000.0, "cooling": 0.90, "type": "server_heavy"}
    elif "SRV-LINUX" in name:
        return {"ram_total_gb": 64.0, "disk_total_gb": 2000.0, "cooling": 0.85, "type": "server_standard"}
    elif "WKST-WIN" in name:
        return {"ram_total_gb": 16.0, "disk_total_gb": 512.0, "cooling": 0.50, "type": "workstation"}
    else:
        return {"ram_total_gb": 8.0, "disk_total_gb": 256.0, "cooling": 0.60, "type": "default"}

hw = get_hardware_profile(machine)

# --- 3. ETAT INTERNE REALISTE (En Gigaoctets) ---
internal_state = {
    "ram_used_gb": hw["ram_total_gb"] * random.uniform(0.15, 0.25),
    "disk_used_gb": hw["disk_total_gb"] * random.uniform(0.40, 0.60),
    "cpu_target": 5.0,
    "temp_current": 35.0,
    "users_count": 0 if "server" in hw["type"] else 1
}

# --- 4. DICTIONNAIRE D'EXPORT ---
stats = {
    "cpu": 0.0, "gpu": 0.0, "ram": 0.0, "disk": 0.0, "temp": 0.0, "users": 0
}

def run_simulation_loop():
    print(f"[{machine}] Specs physiques chargees : {hw['ram_total_gb']}Go RAM | {hw['disk_total_gb']}Go Disque", flush=True)
    current_cpu = 5.0

    while True:
        if hw["type"] == "workstation":
            if random.randint(1, 10) == 1:
                internal_state["cpu_target"] = random.uniform(40.0, 95.0)
                internal_state["ram_used_gb"] += random.uniform(0.2, 1.5)
            else:
                internal_state["cpu_target"] = random.uniform(2.0, 15.0)
            if random.randint(1, 20) == 1:
                internal_state["users_count"] = random.choice([0, 1, 1])
        else:
            if random.randint(1, 20) == 1:
                internal_state["cpu_target"] = random.uniform(60.0, 90.0)
            else:
                internal_state["cpu_target"] = max(5.0, min(80.0, internal_state["cpu_target"] + random.uniform(-5, 5)))
            internal_state["ram_used_gb"] += random.uniform(0.01, 0.08)
            if random.randint(1, 15) == 1:
                internal_state["users_count"] = max(0, min(5, internal_state["users_count"] + random.choice([-1, 0, 1])))

        internal_state["ram_used_gb"] = min(internal_state["ram_used_gb"], hw["ram_total_gb"])
        internal_state["disk_used_gb"] = min(internal_state["disk_used_gb"] + 0.005, hw["disk_total_gb"])
        current_cpu += (internal_state["cpu_target"] - current_cpu) * 0.3
        
        temp_target = 30.0 + (current_cpu * 0.6)
        internal_state["temp_current"] += (temp_target - internal_state["temp_current"]) * (1.0 - hw["cooling"])
        internal_state["temp_current"] += random.uniform(-0.3, 0.3)

        stats["cpu"] = current_cpu
        stats["gpu"] = current_cpu * 0.3 + random.uniform(0, 5)
        stats["ram"] = (internal_state["ram_used_gb"] / hw["ram_total_gb"]) * 100.0
        stats["disk"] = (internal_state["disk_used_gb"] / hw["disk_total_gb"]) * 100.0
        stats["temp"] = internal_state["temp_current"]
        stats["users"] = internal_state["users_count"]

        time.sleep(2)

# --- 5. API FLASK ---
app = Flask(__name__)

@app.route('/stats')
def stats_api():
    return jsonify({
        "machine": machine,
        "os": os_type,
        "cpu": round(stats["cpu"], 2),
        "ram": round(stats["ram"], 2),
        "disk": round(stats["disk"], 2),
        "temp": round(stats["temp"], 2),
        "users": stats["users"]
    })

if __name__ == "__main__":
    threading.Thread(target=run_simulation_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)