import time
import os
import random
import threading
import sys
from flask import Flask, jsonify, request

# *** CONFIGURATION ***
machine = os.environ.get('MACHINE_NAME', 'Inconnu')
os_type = os.environ.get('OS_TYPE', 'Inconnu')

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

# *** ETAT INTERNE ***
internal_state = {
    "ram_used_gb": hw["ram_total_gb"] * random.uniform(0.15, 0.25),
    "disk_used_gb": hw["disk_total_gb"] * random.uniform(0.40, 0.60),
    "cpu_target": 5.0,
    "temp_current": 35.0,
    "users_count": 0 if "server" in hw["type"] else 1,
    "is_mining": False,
    "chrome_tabs": 0,
    "is_ransomware": False,
    "is_ddos": False,
    "is_repairing": False
}

stats = {"cpu": 0.0, "gpu": 0.0, "ram": 0.0, "disk": 0.0, "temp": 0.0, "users": 0}

# *** BOUCLE DE SIMULATION ***
def run_simulation_loop():
    print(f"[{machine}] Agent fully operational.", flush=True)
    current_cpu = 5.0

    while True:
        if not (internal_state["is_mining"] or internal_state["is_ransomware"] or internal_state["is_ddos"]):
            if hw["type"] == "workstation":
                internal_state["cpu_target"] = random.uniform(40.0, 95.0) if random.randint(1, 10) == 1 else random.uniform(2.0, 15.0)
            else:
                internal_state["cpu_target"] = max(5.0, min(80.0, internal_state["cpu_target"] + random.uniform(-5, 5)))

        cpu_to_use = internal_state["cpu_target"] + (internal_state["chrome_tabs"] * 4.0)
        ram_to_use = internal_state["ram_used_gb"] + (internal_state["chrome_tabs"] * 0.8)
        users_to_show = internal_state["users_count"]

        if internal_state["is_mining"]: cpu_to_use = 100.0
        if internal_state["is_ransomware"]:
            cpu_to_use = 95.0
            internal_state["disk_used_gb"] = min(hw["disk_total_gb"], internal_state["disk_used_gb"] + (hw["disk_total_gb"] * 0.05))
        if internal_state["is_ddos"]:
            cpu_to_use = 100.0
            users_to_show = random.randint(8000, 15000)
            
        if internal_state["is_repairing"]:
            cpu_to_use = max(cpu_to_use, 35.0)

        cpu_to_use = min(cpu_to_use, 100.0)
        ram_to_use = min(ram_to_use, hw["ram_total_gb"])
        current_cpu += (cpu_to_use - current_cpu) * 0.4
        
        temp_target = 30.0 + (current_cpu * 0.6)
        internal_state["temp_current"] += (temp_target - internal_state["temp_current"]) * (1.0 - hw["cooling"])

        stats["cpu"] = current_cpu
        stats["gpu"] = current_cpu * 0.3 + random.uniform(0, 5)
        stats["ram"] = (ram_to_use / hw["ram_total_gb"]) * 100.0
        stats["disk"] = (internal_state["disk_used_gb"] / hw["disk_total_gb"]) * 100.0
        stats["temp"] = internal_state["temp_current"]
        stats["users"] = users_to_show

        print(f"[{machine}] STATS > CPU: {stats['cpu']:.1f}% | GPU: {stats['gpu']:.1f}% | RAM: {stats['ram']:.1f}% | DISK: {stats['disk']:.1f}% | TEMP: {stats['temp']:.1f}C | USR: {stats['users']}", flush=True)
        time.sleep(2)

# *** DEFENSES ***
def perform_antivirus():
    internal_state["is_repairing"] = True
    print(f"[{machine}] [ANTIVIRUS] Analyse en cours (0%)...", flush=True)
    time.sleep(3)
    print(f"[{machine}] [ANTIVIRUS] Destruction des malwares en cours...", flush=True)
    time.sleep(3)
    internal_state["is_mining"] = False
    internal_state["is_ransomware"] = False
    internal_state["cpu_target"] = 5.0
    print(f"[{machine}] [ANTIVIRUS] Termine. Systeme OK.", flush=True)
    time.sleep(2)
    internal_state["is_repairing"] = False

def perform_ddos_mitigation():
    internal_state["is_repairing"] = True
    print(f"[{machine}] [FIREWALL] Analyse du trafic entrant anormal...", flush=True)
    time.sleep(3)
    print(f"[{machine}] [FIREWALL] Routage des requetes vers un trou noir (Sinkhole)...", flush=True)
    time.sleep(3)
    internal_state["is_ddos"] = False
    internal_state["cpu_target"] = 5.0
    print(f"[{machine}] [FIREWALL] Trafic rejete. Charge reseau normalisee.", flush=True)
    time.sleep(2)
    internal_state["is_repairing"] = False

# *** API ***
app = Flask(__name__)

@app.route('/stats')
def stats_api():
    return jsonify({
        "machine": machine, "os": os_type, "cpu": round(stats["cpu"], 2),
        "gpu": round(stats["gpu"], 2), "ram": round(stats["ram"], 2),
        "disk": round(stats["disk"], 2), "temp": round(stats["temp"], 2), "users": stats["users"]
    })

@app.route('/trigger')
def trigger_api():
    action = request.args.get('action')
    if action == "open_chrome":
        internal_state["chrome_tabs"] += 3
    elif action == "close_chrome":
        if internal_state["chrome_tabs"] > 0: internal_state["chrome_tabs"] = 0
    elif action == "virus_on":
        internal_state["is_mining"] = True
    elif action == "ransomware":
        internal_state["is_ransomware"] = True
    elif action == "ddos":
        internal_state["is_ddos"] = True
    elif action == "virus_off":
        threading.Thread(target=perform_antivirus).start()
    elif action == "ddos_off":
        threading.Thread(target=perform_ddos_mitigation).start()
    elif action == "clean":
        internal_state["disk_used_gb"] = hw["disk_total_gb"] * 0.2
        internal_state["chrome_tabs"] = 0
    return "OK"

if __name__ == "__main__":
    try:
        threading.Thread(target=run_simulation_loop, daemon=True).start()
        import logging
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print(f"\n[{machine}] Shutdown. Au revoir !")
        sys.exit(0)