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
            
            # Système d'anti-spam : on n'envoie le mail qu'une fois par session
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)