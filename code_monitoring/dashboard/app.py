# -*- coding: utf-8 -*-
from flask import Flask, render_template, abort
import sqlite3
import os
from visualisation import update_all_graphs

app = Flask(__name__)
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
def inject_machines():
    # Rend la liste des machines disponible dans TOUS les templates (pour la navbar)
    return dict(nav_machines=PARC_INFORMATIQUE)


@app.route("/")
def index():
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
    # On passe bien nav_machines pour la barre de navigation
    return render_template("index.html", graphs=compare_graphs, nav_machines=PARC_INFORMATIQUE)
@app.route("/asset/<name>")
def asset_dashboard(name):
    if name not in PARC_INFORMATIQUE:
        abort(404)
    
    table_name = name.replace("-", "").replace("_", "")
    update_all_graphs([name])
    
    # On utilise des clés SANS ACCENTS pour le dictionnaire Python
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