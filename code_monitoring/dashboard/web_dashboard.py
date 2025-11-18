#!/usr/bin/env python3
from flask import Flask, render_template
import sqlite3
import os

app = Flask(__name__)

# Chemin vers le dossier où les fichiers SVG sont stockés
shared_folder = "/media/sf_ams_server/"

# Fonction pour récupérer les données des 10 derniers relevés de la table system_data
def get_data():
    conn = sqlite3.connect("monitoring.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cpu_usage, ram_usage, disk_usage, users_count, process_count, timestamp
        FROM system_data
        ORDER BY timestamp DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

# Fonction pour récupérer la dernière alerte
def get_last_alert():
    conn = sqlite3.connect("monitoring.db")
    cursor = conn.cursor()
    cursor.execute("SELECT message, timestamp FROM alerts ORDER BY timestamp DESC LIMIT 1")
    alert = cursor.fetchone()
    conn.close()
    return alert

@app.route("/")
def index():
    # Récupérer les dernières données de la base de données
    data = get_data()

    # Vérifie que les fichiers SVG existent dans le dossier partagé
    graph_files = [
        'ram_history.svg',
        'cpu_history.svg',
        'disk_history.svg',
        'users_history.svg',
        'process_history.svg'
    ]
    
    graphs = []
    for graph in graph_files:
        if os.path.exists(os.path.join(shared_folder, graph)):
            graphs.append(graph)

    # Récupérer la dernière alerte depuis la base de données
    alert = get_last_alert()

    # Passer les données, les graphiques et les alertes au template
    return render_template("index.html", data=data, graphs=graphs, alert=alert)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
