# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
import sqlite3
import os
import sys
import bcrypt
import pyotp
import qrcode
import base64
from io import BytesIO
import json
import uuid
import secrets
import string
import unicodedata
import docker
from functools import wraps
from datetime import timedelta, datetime

# On ajoute le dossier parent au PATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

# Clé secrète pour session et flash (les alertes)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-key-very-weak')

# GESTION SÉCURISÉE DES SESSIONS (CYBER)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

DB_PATH = "/app/data/monitoring.db"
JSON_PATH = "/app/data/Users/users_docker.json"

PARC_INFORMATIQUE = ["linux-srv-1", "linux-srv-2", "win-wkst-1", "win-wkst-2", "win-srv-indispensable"]

# Nom "de base" du réseau (fallback si la recherche dynamique échoue).
RESEAU_PRINCIPAL = "tp-docker-projet-annuel_monitoring-net"


def get_target_network_name():
 



    if docker_client is None:
        return RESEAU_PRINCIPAL
    try:
        for net in docker_client.networks.list():
            if "tp-docker-projet-annuel_monitoring-net" in net.name:
                return net.name
    except Exception as e:
        print(f"Erreur recherche réseau : {e}")
    return RESEAU_PRINCIPAL

# Client Docker unique, réutilisé partout (évite de recréer une connexion à chaque requête)
try:
    docker_client = docker.from_env()
except Exception as e:
    print(f"Impossible de se connecter au démon Docker : {e}")
    docker_client = None


# ========================================================
# 1. DÉCORATEURS DE SÉCURITÉ 
# ========================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Sécurité RBAC : Si le rôle n'est pas admin, on bloque immédiatement
        if session.get("role") != "admin":
            flash("Accès refusé : Vous devez être Administrateur pour effectuer cette action.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


# ========================================================
# 2. FONCTIONS DE RÉCUPÉRATION DE DONNÉES
# ========================================================


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


def get_container_status(nom_conteneur):
    """
    Retourne l'état réel d'un conteneur :
    - 'running'  : allumé et connecté au réseau
    - 'isolated' : allumé mais déconnecté de tout réseau (containment)
    - 'stopped'  : éteint / arrêté
    - 'unknown'  : conteneur introuvable ou daemon Docker inaccessible
    """
    if docker_client is None:
        return "unknown"
    try:
        container = docker_client.containers.get(nom_conteneur)
        container.reload()  # rafraîchit les attrs (évite un état obsolète)

        if container.status != "running":
            return "stopped"

        networks = container.attrs['NetworkSettings']['Networks']
        if not networks:
            return "isolated"

        return "running"
    except docker.errors.NotFound:
        return "unknown"
    except Exception as e:
        print(f"Erreur récupération statut {nom_conteneur} : {e}")
        return "unknown"


@app.context_processor
def inject_global_data():
    global_crises = []
    try:
        from detetction_de_crises.detection_de_crise import check_all_assets
        global_crises = check_all_assets(PARC_INFORMATIQUE)

        if global_crises and not session.get('alert_sent'):
            from alertes.envoie_mail import send_combined_alert
            send_combined_alert(global_crises)
            session['alert_sent'] = True
        elif not global_crises:
            session.pop('alert_sent', None)
    except Exception as e:
        print(f"Erreur monitoring global: {e}")

    # Statut de chaque machine, utilisé pour le point de couleur dans la nav
    nav_status = {name: get_container_status(name) for name in PARC_INFORMATIQUE}

    return dict(
        nav_machines=PARC_INFORMATIQUE,
        current_crises=global_crises,
        nav_status=nav_status
    )
def save_user_totp_secret(username, secret):
    """Sauvegarde le secret MFA dans la base de données JSON"""
    try:
        with open(JSON_PATH, "r") as f:
            accounts = json.load(f)
        
        if username in accounts:
            accounts[username]['totp_secret'] = secret
            with open(JSON_PATH, "w") as f:
                json.dump(accounts, f, indent=4)
    except Exception as e:
        print(f"Erreur d'écriture du secret MFA : {e}")

# ========================================================
# 3. ROUTES STANDARD ET AUTHENTIFICATION
# ========================================================

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

        # 1ère ÉTAPE : Vérification Mot de passe
        if user_data and bcrypt.checkpw(password_input.encode('utf-8'), user_data["password"].encode('utf-8')):
            if user_data.get("blocked"):
                flash("Ce compte a été suspendu par un administrateur.", "danger")
                return render_template("login.html")

            # On ne connecte pas encore l'utilisateur (Pas de session["user"] !). 
            # On stocke juste temporairement ses infos pour le MFA.
            session['pre_auth_user'] = username
            session['pre_auth_role'] = user_data.get("role", "user")
            session['pre_auth_uuid'] = user_data.get("id")

            # A-t-il déjà configuré son MFA ?
            if not user_data.get("totp_secret"):
                return redirect(url_for("setup_mfa"))
            else:
                return redirect(url_for("verify_mfa"))
        else:
            flash("Identifiants incorrects.", "danger")

    return render_template("login.html")


@app.route("/setup_mfa", methods=["GET", "POST"])
def setup_mfa():
    # Sécurité : vérifier qu'il a bien passé l'étape du mot de passe
    if 'pre_auth_user' not in session:
        return redirect(url_for("login"))

    username = session['pre_auth_user']

    if request.method == "POST":
        token = request.form.get("token")
        secret = session.get('temp_mfa_secret')

        totp = pyotp.TOTP(secret)
        if totp.verify(token):
            # Le code est bon, on valide la configuration et on le sauvegarde
            save_user_totp_secret(username, secret)
            
            # On ouvre la vraie session
            session.permanent = True 
            session["user"] = username
            session["role"] = session.get('pre_auth_role')
            session["uuid"] = session.get('pre_auth_uuid')
            
            # Nettoyage des variables temporaires
            session.pop('pre_auth_user', None)
            session.pop('temp_mfa_secret', None)
            
            flash("MFA configuré avec succès ! Bienvenue sur le SOC.", "success")
            return redirect(url_for("index"))
        else:
            flash("Code incorrect. Veuillez vérifier l'application.", "danger")

    # Requête GET : On génère le QR Code
    if 'temp_mfa_secret' not in session:
        session['temp_mfa_secret'] = pyotp.random_base32()
        
    secret = session['temp_mfa_secret']
    
    # Création de l'URI pour l'application Authenticator
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=username, 
        issuer_name="CyberMonitors SOC"
    )
    
    # Génération de l'image QR Code directement en mémoire (pas besoin de sauvegarder de fichier)
    img = qrcode.make(totp_uri)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    return render_template("setup_mfa.html", qr_code=qr_b64, secret=secret)


@app.route("/verify_mfa", methods=["GET", "POST"])
def verify_mfa():
    if 'pre_auth_user' not in session:
        return redirect(url_for("login"))

    username = session['pre_auth_user']

    if request.method == "POST":
        token = request.form.get("token")
        
        # Récupération du secret depuis la BDD JSON
        with open(JSON_PATH, "r") as f:
            accounts = json.load(f)
        secret = accounts.get(username, {}).get("totp_secret")

        if not secret:
            flash("Erreur fatale MFA.", "danger")
            return redirect(url_for("login"))

        totp = pyotp.TOTP(secret)
        if totp.verify(token):
            # Code valide, accès autorisé !
            session.permanent = True 
            session["user"] = username
            session["role"] = session.get('pre_auth_role')
            session["uuid"] = session.get('pre_auth_uuid')
            
            session.pop('pre_auth_user', None)
            
            return redirect(url_for("index"))
        else:
            flash("Code MFA invalide.", "danger")

    return render_template("verify_mfa.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    try:
        from detetction_de_crises.detection_de_crise import check_all_assets
        crises = check_all_assets(PARC_INFORMATIQUE)

        if crises:
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
@login_required
def asset_dashboard(name):
    # 1. Vérification globale : L'asset existe-t-il ?
    if name not in PARC_INFORMATIQUE:
        abort(404)

    # 2. Vérification du périmètre de sécurité (Isolation logique)
    try:
        with open(JSON_PATH, "r") as f:
            accounts = json.load(f)
    except Exception:
        flash("Erreur système : Impossible de vérifier vos autorisations.", "danger")
        return redirect(url_for("index"))

    user_data = accounts.get(session["user"], {})
    user_assets = user_data.get("assigned_assets", PARC_INFORMATIQUE)

    if name not in user_assets:
        flash("Accès Refusé : Cet équipement n'est pas dans votre périmètre d'autorisation.", "danger")
        return redirect(url_for("index"))

    # 3. Chargement des données techniques
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
            "graphs": graphs,
            "status": get_container_status(name)  # 'running' | 'isolated' | 'stopped' | 'unknown'
        }
    except Exception as e:
        print(f"Erreur lors du traitement de l'asset {name}: {e}")
        abort(500)

    return render_template("asset.html", asset=data)

@app.route("/profil")
@login_required
def profil():
    try:
        with open(JSON_PATH, "r") as f:
            accounts = json.load(f)
        user_info = accounts.get(session["user"], {})
    except Exception:
        user_info = {}

    data = {
        "username": session["user"],
        "role": session.get("role", "user"),
        "uuid": user_info.get("id", "Non défini"),
        "blocked": user_info.get("blocked", False),
        "force_reset": user_info.get("force_reset", False)
    }
    return render_template("profil.html", user_data=data)


# ========================================================
# 4. ORCHESTRATION ET COMMANDES (API SOAR / C2)
# ========================================================

# Fonction utilitaire pour le nommage IAM
def generate_username(prenom, nom, role, accounts):
    """Génère un identifiant type j.dupont-soc sans accents"""
    # Nettoyage des accents et minuscules
    p = unicodedata.normalize('NFD', prenom).encode('ascii', 'ignore').decode('utf-8').lower()
    n = unicodedata.normalize('NFD', nom).encode('ascii', 'ignore').decode('utf-8').lower()
    
    suffix = "-adm" if role == "admin" else "-soc" if role == "monitor" else "-usr"
    base_username = f"{p[0]}.{n}{suffix}"
    
    # Gestion des doublons (j.dupont-usr, j.dupont-usr2, etc.)
    final_username = base_username
    counter = 2
    while final_username in accounts:
        final_username = f"{base_username}{counter}"
        counter += 1
        
    return final_username

def generate_strong_password(length=12):
    """Génère un mot de passe temporaire fort (12 chars min)"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = ''.join(secrets.choice(alphabet) for i in range(length))
        if (any(c.islower() for c in pwd) and any(c.isupper() for c in pwd) 
            and sum(c.isdigit() for c in pwd) >= 3 and any(c in "!@#$%^&*" for c in pwd)):
            return pwd

@app.route("/create_account", methods=["GET", "POST"])
@login_required
def create_account():
    creator_role = session.get("role")
    if creator_role not in ["admin", "monitor"]:
        flash("Accès refusé : Seuls les administrateurs et analystes peuvent créer des comptes.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        prenom = request.form.get("prenom").strip()
        nom = request.form.get("nom").strip()
        email = request.form.get("email").strip()
        new_role = request.form.get("new_role").strip().lower()
        assigned_assets = request.form.getlist("assets") # Liste des assets cochés

        # Règle métier : Un Monitor ne peut pas créer un Admin
        if creator_role == "monitor" and new_role == "admin":
            flash("Erreur d'élévation : Vous n'avez pas l'autorisation de créer un compte Administrateur.", "danger")
            return redirect(url_for("create_account"))

        # Règle métier : Forcer l'assignation d'assets pour le rôle 'user'
        if new_role == "user" and not assigned_assets:
            flash("Un compte 'Utilisateur Métier' doit avoir au moins un équipement assigné.", "danger")
            return redirect(url_for("create_account"))

        try:
            with open(JSON_PATH, "r") as f:
                accounts = json.load(f)
        except Exception:
            flash("Erreur fatale : Base de données JSON introuvable.", "danger")
            return redirect(url_for("index"))

        # Génération IAM
        new_username = generate_username(prenom, nom, new_role, accounts)
        temp_password = generate_strong_password()
        hashed_password = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Si le rôle n'est pas 'user', il a accès à tout par défaut
        if new_role != "user":
            assigned_assets = PARC_INFORMATIQUE

        # Création de l'objet utilisateur
        new_user_data = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password": hashed_password,
            "role": new_role,
            "assigned_assets": assigned_assets, # <-- Périmètre cloisonné
            "blocked": False,
            "force_reset": True, 
            "reset_by_admin": False,
            "totp_secret": None
        }

        accounts[new_username] = new_user_data
        
        try:
            with open(JSON_PATH, "w") as f:
                json.dump(accounts, f, indent=4)
                
            # --- Envoi de l'email ---
            from alertes.envoie_mail import send_email # Adapte l'import selon ta fonction exacte
            sujet = "Bienvenue sur le SOC CyberMonitors - Vos identifiants"
            corps = f"""
            Bonjour {prenom},
            
            Votre compte d'accès à la plateforme CyberMonitors a été provisionné.
            
            Identifiant : {new_username}
            Mot de passe temporaire : {temp_password}
            
            Lors de votre première connexion, il vous sera demandé de modifier ce mot de passe (12 caractères minimum) et de configurer votre application MFA (Google Authenticator).
            
            Cordialement,
            L'équipe SOC
            """
            # Assure-toi que ta fonction send_email accepte bien (destinataire, sujet, corps)
            send_email(email, sujet, corps) 
            # ------------------------

            flash(f"Compte '{new_username}' provisionné. Un email d'invitation a été envoyé.", "success")
        except Exception as e:
            flash(f"Erreur technique lors de la création : {e}", "danger")
            
        return redirect(url_for("create_account"))

    return render_template("create_account.html", creator_role=creator_role, parc=PARC_INFORMATIQUE)

def est_isole(container):
    """Retourne True si le conteneur n'est connecté à aucun réseau."""
    networks = container.attrs['NetworkSettings']['Networks']
    return len(networks) == 0


@app.route("/api/machine/action", methods=["POST"])
@login_required
@admin_required
def machine_action():
    action = request.form.get("action")
    machine_name = request.form.get("machine")

    if machine_name not in PARC_INFORMATIQUE:
        abort(400, description="Machine inconnue du parc informatique.")

    if docker_client is None:
        flash("Erreur : connexion au daemon Docker indisponible.", "danger")
        return redirect(request.referrer or url_for("index"))

    nom_conteneur = machine_name

    try:
        container = docker_client.containers.get(nom_conteneur)
        container.reload()  # on force le rafraîchissement des attributs

        # ---- Garde-fous serveur : on revérifie l'état réel avant d'agir ----
        # (le front désactive déjà les boutons, mais on ne fait jamais confiance
        # uniquement au HTML : un curl direct doit être bloqué pareil)
        etat_actuel = "stopped" if container.status != "running" else (
            "isolated" if est_isole(container) else "running"
        )

        if action == "start" and etat_actuel != "stopped":
            flash(f"{machine_name} est déjà allumé.", "warning")
            return redirect(request.referrer or url_for("index"))

        if action == "stop" and etat_actuel == "stopped":
            flash(f"{machine_name} est déjà éteint.", "warning")
            return redirect(request.referrer or url_for("index"))

        if action == "isolate" and etat_actuel != "running":
            flash(f" Action impossible : {machine_name} doit être allumé et connecté pour être isolé.", "warning")
            return redirect(request.referrer or url_for("index"))

        if action == "reconnect" and etat_actuel != "isolated":
            flash(f" {machine_name} n'est pas isolé, rien à reconnecter.", "warning")
            return redirect(request.referrer or url_for("index"))
        # ----------------------------------------------------------------

        if action == "start":
            container.start()
            flash(f" [Docker] Conteneur {machine_name} démarré avec succès.", "success")

        elif action == "stop":
            container.stop()
            flash(f" [Docker] Conteneur {machine_name} arrêté proprement.", "warning")

        elif action == "restart":
            container.restart()
            flash(f"[Docker] Conteneur {machine_name} redémarré.", "info")

        elif action == "isolate":
            networks = container.attrs['NetworkSettings']['Networks']
            for net_name in networks:
                network = docker_client.networks.get(net_name)
                network.disconnect(container, force=True)
            container.reload()
            if est_isole(container):
                flash(f" [URGENCE SOC] {machine_name} isolé. Coupure réseau confirmée (Containment).", "danger")
            else:
                flash(f" Échec de l'isolement de {machine_name}, réseau encore actif.", "danger")

        elif action == "reconnect":
            nom_reseau = get_target_network_name()
            print(f"[DEBUG reconnect] Tentative de connexion de {nom_conteneur} au réseau '{nom_reseau}'")
            network = docker_client.networks.get(nom_reseau)
            network.connect(container)
            container.reload()
            if est_isole(container):
                flash(f" Échec : {machine_name} semble toujours isolé après tentative de reconnexion.", "danger")
            else:
                flash(f" [Docker] {machine_name} reconnecté au réseau '{nom_reseau}'.", "success")

    except docker.errors.NotFound as e:
        flash(f"Erreur : conteneur ou réseau '{nom_conteneur}' introuvable ({e}).", "danger")
    except docker.errors.APIError as e:
        flash(f"Erreur de permissions Docker : {str(e)}", "danger")
    except Exception as e:
        print(f"Erreur d'orchestration Docker : {e}")
        flash("Erreur technique lors de l'exécution de l'action.", "danger")

    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)
