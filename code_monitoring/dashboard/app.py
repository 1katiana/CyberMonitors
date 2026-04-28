# -*- coding: utf-8 -*-
from flask import Flask, render_template, abort, flash, session
import sqlite3
import os
import sys

#  On ajoute le dossier parent au PATH 
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

#  pour session et flash (les alertes)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-key-very-weak')

DB_PATH = "/app/data/monitoring.db"
PARC_INFORMATIQUE = ["linux-srv-1", "linux-srv-2", "win-wkst-1", "win-wkst-2", "win-srv-indispensable"]

def get_machine_data(machine_table, limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT cpu_usage, ram_usage, disk_usage, temp, users_count, timestamp FROM {machine_table} ORDER BY timestamp DESC LIMIT {limit}")
        return cursor.fetchall()
    except Exception as e:
        print(f"Erreur SQL : {e}")
        return []
    finally:
        conn.close()


@app.context_processor
def inject_global_data():
    # On initialise une liste vide pour les crises
    global_crises = []
    
    try:
        from detetction_de_crises.detection_de_crise import check_all_assets
        global_crises = check_all_assets(PARC_INFORMATIQUE)
        
        # Logique d'envoi de mail (optionnelle ici ou dans l'index)
        if global_crises and not session.get('alert_sent'):
            from alertes.envoie_mail import send_combined_alert
            send_combined_alert(global_crises)
            session['alert_sent'] = True
        elif not global_crises:
            session.pop('alert_sent', None)
            
    except Exception as e:
        print(f"Erreur monitoring global: {e}")

    # On rend 'nav_machines' ET 'current_crises' disponibles partout
    return dict(
        nav_machines=PARC_INFORMATIQUE,
        current_crises=global_crises
    )

@app.route("/")
def index():
    # CORRECTION DES IMPORTS AVEC LES DOSSIERS SPECIFIQUES
    try:
        # Import depuis le dossier 'detetction_de_crises'
        from detetction_de_crises.detection_de_crise import check_all_assets
        crises = check_all_assets(PARC_INFORMATIQUE)
        
        if crises:
            # Import depuis le dossier 'alertes'
            from alertes.envoie_mail import send_combined_alert
            
            # Syst�me d'anti-spam : on n'envoie le mail qu'une fois par session
            if not session.get('alert_sent'):
                send_combined_alert(crises)
                session['alert_sent'] = True
            
            for c in crises:
                flash(f"ALERTE sur {c['asset']}: {', '.join(c['details'])}", "danger")
    except Exception as e:
        print(f"Erreur systeme d'alerte: {e}")

    try:
        from visualisation import generate_comparison_graphs
        generate_comparison_graphs(PARC_INFORMATIQUE)
    except Exception as e:
        print(f"Erreur generation accueil: {e}")
        
    compare_graphs = {
        "Charge CPU Global": "graphs/compare_cpu.svg",
        "Usage RAM Global": "graphs/compare_ram.svg",
        "Espace Disque Global": "graphs/compare_disk.svg",
        "Utilisateurs Connectes": "graphs/compare_users.svg"
    }
    return render_template("index.html", graphs=compare_graphs)

@app.route("/asset/<name>")
def asset_dashboard(name):
    if name not in PARC_INFORMATIQUE:
        abort(404)
    
    from visualisation import update_all_graphs
    table_name = name.replace("-", "").replace("_", "")
    update_all_graphs([name])
    
    graphs = {
        "CPU": f"graphs/{table_name}_cpu.svg",
        "RAM": f"graphs/{table_name}_ram.svg",
        "Disque": f"graphs/{table_name}_disk.svg",
        "Temperature": f"graphs/{table_name}_temp.svg",
        "Utilisateurs": f"graphs/{table_name}_users.svg"
    }
    
    data = {
        "name": name,
        "history": get_machine_data(table_name, limit=10),
        "graphs": graphs
    }
    return render_template("asset.html", asset=data)
    import socket
from flask import jsonify

#---------- Code Arnaud --------------

import socket
import json
from flask import jsonify, request

def docker_action(container_name, action):
    """Communique avec le moteur Docker via le socket UNIX natif"""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect("/var/run/docker.sock")
        req = f"POST /containers/{container_name}/{action} HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        sock.sendall(req.encode('utf-8'))
        
        response = b""
        while True:
            data = sock.recv(4096)
            if not data:
                break
            response += data
        sock.close()
        
        resp_str = response.decode('utf-8', errors='ignore')
        # On renvoie le code exact au lieu de 'OK' pour éviter les bugs d'affichage
        if "HTTP/1.1 204" in resp_str:
            return True, "204"
        elif "HTTP/1.1 304" in resp_str:
            return True, "304"
        else:
            status_line = resp_str.split('\r\n')[0] if '\r\n' in resp_str else "Erreur Inconnue"
            return False, status_line
    except Exception as e:
        return False, str(e)

@app.route("/api/_internal_docker/<name>/<action>")
def internal_docker(name, action):
    """Route invisible utilisee par le JavaScript pour executer l'action en tâche de fond"""
    if name not in PARC_INFORMATIQUE or action not in ["start", "stop", "restart"]:
        return jsonify({"success": False, "details": "Requete invalide"})
        
    success, details = docker_action(name, action)
    return jsonify({"success": success, "details": details})

@app.route("/api/machine/<targets>/<action>")
def control_machine(targets, action):
    if action not in ["start", "stop", "restart"]:
        return "Erreur : Action interdite", 400
        
    # 1. Analyse des cibles
    if targets.lower() in ["all", "toutes"]:
        machines_a_traiter = PARC_INFORMATIQUE
    else:
        machines_a_traiter = [m.strip() for m in targets.split(',')]

    # 2. Vérification des machines
    machines_inconnues = [m for m in machines_a_traiter if m not in PARC_INFORMATIQUE]
    if machines_inconnues:
        return f"Erreur : Machines inconnues : {', '.join(machines_inconnues)}", 404

    # 3. Préparation des variables pour la page
    page_precedente = request.referrer or "/"
    machines_json = json.dumps(machines_a_traiter)

    # 4. Génération de l'interface dynamique
    html = f"""
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="utf-8">
        <title>Console d'Exécution</title>
        <style>
          body {{ background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
          .card {{ background: #1e1e1e; padding: 30px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 450px; border: 1px solid #333; }}
          h2 {{ margin-top: 0; color: #00adb5; border-bottom: 1px solid #333; padding-bottom: 10px; text-align: center; }}
          table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
          td {{ padding: 10px; border-bottom: 1px solid #2a2a2a; text-align: left; }}
          .status {{ font-weight: bold; }}
          .spinner-mini {{ display: inline-block; width: 12px; height: 12px; border: 2px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: #fff; animation: spin 1s linear infinite; margin-right: 8px; vertical-align: middle; }}
          @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
          .timer-box {{ font-size: 0.9em; color: #888; background: #252525; padding: 10px; border-radius: 4px; text-align: center; display: none; }}
          #seconds {{ color: #00adb5; font-weight: bold; font-size: 1.2em; }}
        </style>
      </head>
      <body>
        <div class="card">
          <h2>Protocole : {action.upper()}</h2>
          <table id="machine-table">
            </table>
          <div id="timer-container" class="timer-box">
            Tâches terminées. Retour dans <span id="seconds">5</span> secondes...
          </div>
        </div>

        <script>
          const machines = {machines_json};
          const action = "{action}";
          const fallbackUrl = "{page_precedente}";
          
          const table = document.getElementById('machine-table');
          
          // Initialisation du tableau avec le statut "En attente"
          machines.forEach(m => {{
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td>${{m}}</td>
              <td id="status-${{m}}" class="status" style="color: #ffc107;">
                <div class="spinner-mini"></div> En attente...
              </td>
            `;
            table.appendChild(tr);
          }});

          async function processMachines() {{
            // On traite chaque machine l'une après l'autre
            for (const m of machines) {{
              const statusCell = document.getElementById(`status-${{m}}`);
              statusCell.innerHTML = `<div class="spinner-mini"></div> En cours...`;
              statusCell.style.color = "#17a2b8";
              
              try {{
                const response = await fetch(`/api/_internal_docker/${{m}}/${{action}}`);
                const data = await response.json();
                
                if (data.success) {{
                    if (data.details === "204") {{
                        statusCell.innerHTML = "✓ Action réussie";
                        statusCell.style.color = "#28a745";
                    }} else if (data.details === "304") {{
                        statusCell.innerHTML = "✓ Déjà dans cet état";
                        statusCell.style.color = "#00adb5";
                    }} else {{
                        statusCell.innerHTML = "✓ Terminé";
                        statusCell.style.color = "#28a745";
                    }}
                }} else {{
                    statusCell.innerHTML = `✗ Erreur (${{data.details}})`;
                    statusCell.style.color = "#dc3545";
                }}
              }} catch (err) {{
                statusCell.innerHTML = "✗ Erreur réseau";
                statusCell.style.color = "#dc3545";
              }}
            }}
            
            // Lancement du compte à rebours 5s SEULEMENT quand tout est fini
            startCountdown();
          }}

          function startCountdown() {{
            document.getElementById('timer-container').style.display = 'block';
            let timeLeft = 5;
            const timerElement = document.getElementById('seconds');
            const countdown = setInterval(() => {{
              timeLeft--;
              timerElement.innerText = timeLeft;
              if (timeLeft <= 0) {{
                clearInterval(countdown);
                window.location.href = fallbackUrl;
              }}
            }}, 1000);
          }}

          // Démarrer automatiquement dès l'ouverture de la page
          window.onload = processMachines;
        </script>
      </body>
    </html>
    """
    return html
    
#------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)