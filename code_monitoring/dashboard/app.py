# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
import sqlite3
import os
import sys
import bcrypt
from functools import wraps
import json
from datetime import timedelta, datetime

# On ajoute le dossier parent au PATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

# pour session et flash (les alertes)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-key-very-weak')

# GESTION SÉCURISÉE DES SESSIONS (CYBER)
# Règle 1 : La session expire après 15 minutes d'inactivité
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)

# Règle 2 : Le cookie est détruit dès qu'on ferme le navigateur
# (Par défaut dans Flask, mais on force le comportement pour la sécurité)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

DB_PATH = "/app/data/monitoring.db"
JSON_PATH = "/app/data/Users/users_docker.json"

PARC_INFORMATIQUE = ["linux-srv-1", "linux-srv-2", "win-wkst-1", "win-wkst-2", "win-srv-indispensable"]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Si 'user' n'est pas enregistré dans la session Flask, on redirige vers le login
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# --- 2. LA ROUTE DE CONNEXION (LOGIN) ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        password_input = request.form.get("password").strip()

        try:
            with open(JSON_PATH, "r") as f:
                accounts = json.load(f)
        except FileNotFoundError:
            flash("Erreur : La base d'utilisateurs est introuvable.", "danger")
            return render_template("login.html")

        user_data = accounts.get(username)

        if user_data and bcrypt.checkpw(password_input.encode('utf-8'), user_data["password"].encode('utf-8')):

            if user_data.get("blocked"):
                flash("Ce compte a été suspendu par un administrateur.", "danger")
                return render_template("login.html")

            # === AJOUT DE SÉCURITÉ ICI ===
            # On dit à Flask que cette session doit suivre les règles d'expiration strictes
            session.permanent = True 
            
            session["user"] = username
            session["role"] = user_data.get("role", "user")
            session["uuid"] = user_data.get("uuid")

            return redirect(url_for("index"))
        else:
            flash("Identifiants incorrects.", "danger")

    return render_template("login.html")
# --- 3. LA ROUTE DE DECONNEXION (LOGOUT) ---
@app.route("/logout")
def logout():
    session.clear() # On vide la session (efface le cookie)
    return redirect(url_for("login"))

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
@login_required  # <-- Bloque l'accès si pas connecté
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

# --- 7. PAGE DE DÉTAIL PAR MACHINE (PROPRE ET UNIQUE) ---
@app.route("/asset/<name>")
@login_required  
def asset_dashboard(name):
    if name not in PARC_INFORMATIQUE:
        abort(404)

    try:
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
    except Exception as e:
        print(f"Erreur lors du traitement de l'asset {name}: {e}")
        abort(500)

    # Ici on passe bien l'objet 'asset=data' dont le template HTML a besoin !
    return render_template("asset.html", asset=data)
@app.route("/profil")
@login_required  # Sécurisé, il faut être connecté
def profil():
    try:
        with open(JSON_PATH, "r") as f:
            accounts = json.load(f)
        user_info = accounts.get(session["user"], {})
    except Exception:
        user_info = {}

    # Données nettoyées et envoyées à la page de profil
    data = {
        "username": session["user"],
        "role": session.get("role", "user"),
        # CORRECTION ICI : Extraction directe de l'UUID depuis le JSON d'Arnaud
        "uuid": user_info.get("id", "Non défini"),
        "blocked": user_info.get("blocked", False),
        "force_reset": user_info.get("force_reset", False)
    }
    
    return render_template("profil.html", user_data=data)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)