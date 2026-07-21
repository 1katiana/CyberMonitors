# -*- coding: utf-8 -*-
import time
import os
import random
import threading
import sys
import sqlite3
import requests
import json  # <-- AJOUT : Pour lire le fichier d'ordres de Katiana
from flask import Flask, jsonify, request

# *** CONFIGURATION ***
machine = os.environ.get('MACHINE_NAME', 'Inconnu')
os_type = os.environ.get('OS_TYPE', 'Inconnu')

# Chemin vers le fichier d'ordres partagé dans le volume Docker /app/data/
ORDRES_PATH = "/app/data/ordres_c2.json"

def get_hardware_profile(name):
    if "win-srv" in name:
        return {"ram_total_gb": 128.0, "disk_total_gb": 4000.0, "cooling": 0.90, "type": "server_heavy"}
    elif "linux-srv" in name:
        return {"ram_total_gb": 64.0, "disk_total_gb": 2000.0, "cooling": 0.85, "type": "server_standard"}
    elif "win-wkst" in name:
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
    "is_repairing": False,
    "is_isolated": False  # <-- AJOUT : Nouvel état cyber pour l'isolation
}

stats = {"cpu": 0.0, "gpu": 0.0, "ram": 0.0, "disk": 0.0, "temp": 0.0, "users": 0}

# *** COMPORTEMENT CYBER : VÉRIFICATION DES ORDRES DE LA PLATEFORME ***
def watch_c2_orders():
    """ Boucle résidente qui surveille le fichier partagé par le Dashboard """
    print(f"[{machine}] [C2 AGENT] Thread de surveillance C2 actif.", flush=True)
    
    while True:
        time.sleep(3) # Vérification toutes les 3 secondes
        
        if not os.path.exists(ORDRES_PATH):
            continue
            
        try:
            with open(ORDRES_PATH, "r") as f:
                ordres = json.load(f)
        except Exception:
            continue

        modifie = False

        for ordre in ordres:
            # L'ordre correspond-il à CETTE machine et n'est pas encore exécuté ?
            if ordre["machine"] == machine and not ordre["execute"]:
                action = ordre["action"]
                print(f"[{machine}] [C2 AGENT] ORDRE REÇU DE LA PLATFORME : {action}", flush=True)
                
                if action == "stop":
                    print(f"[{machine}] [C2 AGENT] Extinction imminente demandée par l'Admin.", flush=True)
                    ordre["execute"] = True
                    with open(ORDRES_PATH, "w") as f:
                        json.dump(ordres, f, indent=4)
                    
                    # Simulation réelle d'extinction : On coupe brutalement le script Python de l'agent.
                    # Le conteneur Docker va crash/s'arrêter et le Dashboard n'aura plus de stats !
                    os._exit(0) 

                elif action == "restart":
                    print(f"[{machine}] [C2 AGENT] Redémarrage en cours...", flush=True)
                    ordre["execute"] = True
                    with open(ORDRES_PATH, "w") as f:
                        json.dump(ordres, f, indent=4)
                    
                    # Pour un redémarrage, on coupe l'agent. Si le docker-compose a un 'restart: always', 
                    # Docker va relancer le conteneur automatiquement au bout de quelques secondes !
                    os._exit(0)

                elif action == "isolate":
                    print(f"[{machine}] [C2 AGENT] ALERTE : Isolation réseau appliquée !", flush=True)
                    internal_state["is_isolated"] = True
                    # On simule l'isolement en coupant les utilisateurs légitimes
                    internal_state["users_count"] = 0
                    ordre["execute"] = True
                    modifie = True

                elif action == "start":
                    print(f"[{machine}] [C2 AGENT] Machine déjà démarrée.", flush=True)
                    internal_state["is_isolated"] = False
                    ordre["execute"] = True
                    modifie = True

        if modifie:
            try:
                with open(ORDRES_PATH, "w") as f:
                    json.dump(ordres, f, indent=4)
            except Exception as e:
                print(f"[{machine}] Erreur écriture réponse C2: {e}", flush=True)


# *** BOUCLE DE SIMULATION ***
def run_simulation_loop():
    print(f"[{machine}] Agent fully operational.", flush=True)
    current_cpu = 5.0

    while True:
        # Si la machine est isolée, elle n'a plus d'activité réseau normale
        if internal_state["is_isolated"]:
            internal_state["cpu_target"] = 1.0 # Activité au repos
            internal_state["users_count"] = 0
        else:
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

# *** ACTION DE NETTOYAGE PROFOND (PRIORITE 1) ***
def perform_full_clean():
    internal_state["is_repairing"] = True
    print(f"[{machine}] [CLEAN] Lancement du nettoyage systeme et BDD...", flush=True)
    
    internal_state["disk_used_gb"] = hw["disk_total_gb"] * 0.2
    internal_state["chrome_tabs"] = 0
    internal_state["is_mining"] = False
    internal_state["is_ransomware"] = False
    internal_state["is_ddos"] = False
    internal_state["cpu_target"] = 5.0
    
    db_path = "/Data/monitoring.db"
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM logs WHERE machine_name = ? AND status = 'CRITIQUE'", (machine,))
            conn.commit()
            conn.close()
            print(f"[{machine}] [CLEAN] BDD mise a jour.", flush=True)
    except Exception as e:
        print(f"[{machine}] [CLEAN] Erreur BDD: {e}", flush=True)

    try:
        requests.post("http://dashboard:8050/api/reset", timeout=2)
        print(f"[{machine}] [CLEAN] Signal de reset envoye au Dashboard.", flush=True)
    except:
        pass

    time.sleep(2)
    internal_state["is_repairing"] = False
    print(f"[{machine}] [CLEAN] Systeme propre et synchronise.", flush=True)

# *** DEFENSES ***
def perform_antivirus():
    internal_state["is_repairing"] = True
    print(f"[{machine}] [ANTIVIRUS] Analyse en cours...", flush=True)
    time.sleep(3)
    internal_state["is_mining"] = False
    internal_state["is_ransomware"] = False
    internal_state["cpu_target"] = 5.0
    print(f"[{machine}] [ANTIVIRUS] Menaces eliminees.", flush=True)
    internal_state["is_repairing"] = False

def perform_ddos_mitigation():
    internal_state["is_repairing"] = True
    print(f"[{machine}] [FIREWALL] Filtrage des paquets suspect...", flush=True)
    time.sleep(3)
    internal_state["is_ddos"] = False
    internal_state["cpu_target"] = 5.0
    print(f"[{machine}] [FIREWALL] Attaque bloquee.", flush=True)
    internal_state["is_repairing"] = False

# *** API ***
app = Flask(__name__)

@app.route('/stats')
def stats_api():
    # Si la machine est isolée, elle refuse de répondre aux requêtes de stats externes (simulation de coupure réseau)
    if internal_state["is_isolated"]:
        return jsonify({"error": "Host isolated from monitoring network."}), 403
        
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
        internal_state["chrome_tabs"] = 0
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
        threading.Thread(target=perform_full_clean).start()
    return "OK"

if __name__ == "__main__":
    try:
        # 1. Démarrage du thread de simulation
        threading.Thread(target=run_simulation_loop, daemon=True).start()
        
        # 2. AJOUT : Démarrage du thread d'écoute C2 de Katiana
        threading.Thread(target=watch_c2_orders, daemon=True).start()
        
        import logging
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        sys.exit(0)