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
from datetime import timedelta
from cryptography.fernet import Fernet
import hmac
import hashlib

# On ajoute le dossier parent au PATH pour pouvoir importer les modules
# maison (detetction_de_crises, alertes, visualisation) qui vivent a cote
# de ce fichier
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

# Cle secrete pour signer les sessions et les messages flash.
# La valeur par defaut ne sert qu'en dev local, en prod elle vient
# toujours de la variable d'environnement FLASK_SECRET
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-key-very-weak')

# Une session expire au bout de 15 minutes d'inactivite, et on la
# renouvelle a chaque requete tant que l'utilisateur reste actif.
# C'est une exigence classique cote SOC : on ne laisse pas trainer
# une session ouverte indefiniment sur un poste partage
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

#DB_PATH = "/app/data/monitoring.db"
#JSON_PATH = "/app/data/Users/users_docker.json"

BASE_DIR = os.environ.get("DATA_DIR", "/app/data")
DB_PATH = os.path.join(BASE_DIR, "monitoring.db")
JSON_PATH = os.path.join(BASE_DIR, "Users", "users_docker.json")


PARC_INFORMATIQUE = ["linux-srv-1", "linux-srv-2", "win-wkst-1", "win-wkst-2", "win-srv-indispensable"]

# Longueur minimale imposee pour tous les mots de passe (creation de compte
# et changement force). Centralise ici pour ne pas avoir un "12" en dur
# a plusieurs endroits du fichier
PASSWORD_MIN_LENGTH = 12

# Nom "de base" du reseau Docker Compose. On garde cette valeur en secours
# au cas ou la recherche dynamique plus bas ne trouve rien
RESEAU_PRINCIPAL = "tp-docker-projet-annuel_monitoring-net"

FERNET_KEY = os.environ.get('FERNET_SECRET_KEY')
cipher = Fernet(FERNET_KEY.encode('utf-8')) if FERNET_KEY else None

def decrypt_val(encrypted_val):
    if not cipher or not encrypted_val or encrypted_val == "Non renseigne":
        return encrypted_val
    try:
        return cipher.decrypt(encrypted_val.encode('utf-8')).decode('utf-8')
    except:
        return encrypted_val


@app.before_request
def check_initialization():
    # Si on n'est pas encore initialisé et qu'on n'est pas sur la route de login
    # on bloque tout pour éviter les erreurs.
    if not os.path.exists("/app/data/.initialized") and request.endpoint != 'static':
        return "Système en cours d'initialisation. Veuillez patienter ou exécuter le script de démarrage."


def get_target_network_name():
    """
    Docker Compose prefixe generalement le nom du reseau avec le nom du
    dossier du projet, du coup on ne peut pas juste taper "monitoring-net"
    en dur et esperer que ca marche partout. Cette fonction va chercher
    le vrai nom du reseau en listant les reseaux existants sur le daemon
    et en gardant celui qui contient notre nom de base
    """
    if docker_client is None:
        return RESEAU_PRINCIPAL
    try:
        for net in docker_client.networks.list():
            if "tp-docker-projet-annuel_monitoring-net" in net.name:
                return net.name
    except Exception as e:
        print(f"Erreur recherche reseau : {e}")
    return RESEAU_PRINCIPAL


# Client Docker unique, cree une seule fois au demarrage de l'app plutot
# que de refaire docker.from_env() a chaque requete (c'est inutilement
# lourd et ca peut echouer bizarrement si on le fait trop souvent)
try:
    docker_client = docker.from_env()
except Exception as e:
    print(f"Impossible de se connecter au demon Docker : {e}")
    docker_client = None


# ========================================================
# 1. DECORATEURS DE SECURITE
# ========================================================
# Ces deux decorateurs sont places tout en haut du fichier expres, avant
# meme les routes qui les utilisent, pour qu'on les ait sous les yeux
# des qu'on ouvre le fichier

def login_required(f):
    """Bloque l'acces a une route si personne n'est connecte (pas de session['user'])"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    A utiliser en plus de login_required sur les routes sensibles
    (actions Docker, gestion des comptes admin...). On verifie le role
    stocke en session, pas dans la base, pour eviter de relire le JSON
    a chaque appel - le role est deja verifie et pose en session au moment
    du login donc c'est fiable
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Acces refuse : Vous devez etre Administrateur pour effectuer cette action.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


# ========================================================
# 2. FONCTIONS DE RECUPERATION DE DONNEES
# ========================================================

def get_machine_data(machine_table, limit=10):
    """
    Va chercher les N dernieres lignes de metriques d'une machine dans
    la base SQLite. Le nom de table est construit a partir du nom de la
    machine (voir asset_dashboard plus bas), donc on reste prudent avec
    le try/except au cas ou la table n'existe pas encore
    """
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
    Renvoie l'etat reel d'un conteneur cote Docker, pas juste son statut
    "running/stopped" : on regarde aussi s'il a encore des interfaces
    reseau, parce qu'un conteneur peut tourner tout en etant isole
    (voir la fonction est_isole plus bas et le bouton "Isoler" du dashboard)

    Valeurs possibles :
    - running  : allume et connecte au reseau
    - isolated : allume mais plus aucune interface reseau (containment)
    - stopped  : eteint / arrete
    - unknown  : conteneur introuvable ou daemon Docker injoignable
    """
    if docker_client is None:
        return "unknown"
    try:
        container = docker_client.containers.get(nom_conteneur)
        container.reload()  # sans ca, container.attrs peut etre perime

        if container.status != "running":
            return "stopped"

        networks = container.attrs['NetworkSettings']['Networks']
        if not networks:
            return "isolated"

        return "running"
    except docker.errors.NotFound:
        return "unknown"
    except Exception as e:
        print(f"Erreur recuperation statut {nom_conteneur} : {e}")
        return "unknown"


@app.context_processor
def inject_global_data():
    """
    On injecte les données globales uniquement si l'utilisateur est connecté.
    Si l'utilisateur n'est pas en session, on retourne des listes vides
    pour ne pas afficher d'alertes ou de navigation sur la page de login.
    """
    # Si pas de session utilisateur, on renvoie tout vide
    if "user" not in session:
        return dict(nav_machines=[], current_crises=[], nav_status={})

    global_crises = []
    
    # Récupération des assets autorisés
    try:
        with open(JSON_PATH, "r") as f:
            accounts = json.load(f)
        user_data = accounts.get(session["user"], {})
        
        # Filtrage : si user, on restreint, sinon on montre tout le parc
        if session.get("role") == "user":
            user_assets = user_data.get("assigned_assets", [])
        else:
            user_assets = PARC_INFORMATIQUE
    except Exception:
        user_assets = []

    # Monitoring uniquement pour les assets autorisés
    try:
        from detetction_de_crises.detection_de_crise import check_all_assets
        global_crises = check_all_assets(user_assets)

        # Gestion des alertes mail (seulement si connecté)
        if global_crises and not session.get('alert_sent'):
            from alertes.envoie_mail import send_combined_alert
            send_combined_alert(global_crises)
            session['alert_sent'] = True
        elif not global_crises:
            session.pop('alert_sent', None)
    except Exception as e:
        print(f"Erreur monitoring : {e}")

    nav_status = {name: get_container_status(name) for name in user_assets}

    return dict(
        nav_machines=user_assets,
        current_crises=global_crises,
        nav_status=nav_status
    )
    
def save_user_totp_secret(username, secret):
    """
    Enregistre le secret TOTP definitif dans users_docker.json une fois
    que l'utilisateur a prouve, en scannant le QR code et en entrant un
    code valide, qu'il a bien configure son application Authenticator.
    Avant cet appel le secret ne vit que dans la session (voir setup_mfa)
    """
    try:
        with open(JSON_PATH, "r") as f:
            accounts = json.load(f)

        if username in accounts:
            accounts[username]['totp_secret'] = secret
            with open(JSON_PATH, "w") as f:
                json.dump(accounts, f, indent=4)
    except Exception as e:
        print(f"Erreur d'ecriture du secret MFA : {e}")


# ========================================================
# 3. AUTHENTIFICATION (login -> reset mot de passe -> MFA)
# ========================================================
# Ces quatre routes forment un seul parcours de connexion en plusieurs
# etapes. On ne pose jamais session["user"] avant d'etre certain que
# TOUTES les etapes obligatoires sont passees (mot de passe correct,
# eventuellement changement de mot de passe si force_reset, puis MFA).
# En attendant, on utilise pre_auth_user comme une sorte de session
# "provisoire" qui prouve juste qu'on a franchi l'etape precedente

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Premiere etape : identifiant + mot de passe. Si c'est bon, on ne
    connecte pas tout de suite l'utilisateur, on le fait juste passer
    en pre-authentification et on l'envoie vers l'etape suivante
    (changement de mot de passe si son compte est neuf, sinon MFA)
    """
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
                flash("Ce compte a ete suspendu par un administrateur.", "danger")
                return render_template("login.html")

            session['pre_auth_user'] = username
            session['pre_auth_role'] = user_data.get("role", "user")
            session['pre_auth_uuid'] = user_data.get("id")

            # Un compte fraichement cree par create_account a toujours
            # force_reset a True : on l'oblige a changer son mot de passe
            # temporaire avant meme de pouvoir configurer son MFA
            if user_data.get("force_reset"):
                return redirect(url_for("force_reset_pwd"))

            if not user_data.get("totp_secret"):
                return redirect(url_for("setup_mfa"))
            else:
                return redirect(url_for("verify_mfa"))
        else:
            flash("Identifiants incorrects.", "danger")

    return render_template("login.html")


@app.route("/force_reset_pwd", methods=["GET", "POST"])
def force_reset_pwd():
    """
    Etape de changement de mot de passe obligatoire, declenchee quand
    le compte a ete cree par un admin avec un mot de passe temporaire
    (force_reset = True). Une fois le nouveau mot de passe valide et
    enregistre, on continue le parcours normal vers le MFA
    """
    if 'pre_auth_user' not in session:
        return redirect(url_for("login"))

    username = session['pre_auth_user']

    if request.method == "POST":
        new_pwd = request.form.get("new_password").strip()
        confirm_pwd = request.form.get("confirm_password").strip()

        if new_pwd != confirm_pwd:
            flash("Les mots de passe ne correspondent pas.", "danger")
            return redirect(url_for("force_reset_pwd"))

        # Verification de la politique de complexite : 12 caracteres,
        # majuscule, minuscule, chiffre et symbole. On liste tout ce qui
        # manque plutot que de s'arreter au premier probleme, c'est plus
        # confortable pour l'utilisateur de tout corriger d'un coup
        missing = []
        if len(new_pwd) < PASSWORD_MIN_LENGTH:
            missing.append(f"{PASSWORD_MIN_LENGTH} caracteres minimum")
        if not any(c.isupper() for c in new_pwd):
            missing.append("une majuscule")
        if not any(c.islower() for c in new_pwd):
            missing.append("une minuscule")
        if not any(c.isdigit() for c in new_pwd):
            missing.append("un chiffre")
        if not any(c in string.punctuation for c in new_pwd):
            missing.append("un symbole specifique")

        if missing:
            flash(f"Mot de passe invalide. Il manque : {', '.join(missing)}", "danger")
            return redirect(url_for("force_reset_pwd"))

        try:
            with open(JSON_PATH, "r") as f:
                accounts = json.load(f)

            stored_hash = accounts[username].get("password", "").encode('utf-8')

            # On interdit de reprendre exactement le meme mot de passe
            # temporaire. Le try/except est la parce que bcrypt.checkpw
            # peut lever une erreur si le hash stocke n'est pas dans un
            # format attendu (compte tres ancien, donnee corrompue...)
            try:
                if bcrypt.checkpw(new_pwd.encode('utf-8'), stored_hash):
                    flash("Le nouveau mot de passe doit etre different de l'ancien.", "danger")
                    return redirect(url_for("force_reset_pwd"))
            except ValueError:
                pass

            new_hashed = bcrypt.hashpw(new_pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            accounts[username]["password"] = new_hashed
            accounts[username]["force_reset"] = False
            accounts[username]["reset_by_admin"] = False

            with open(JSON_PATH, "w") as f:
                json.dump(accounts, f, indent=4)

            flash("Mot de passe mis a jour avec succes. Etape suivante : configuration MFA...", "success")

            if not accounts[username].get("totp_secret"):
                return redirect(url_for("setup_mfa"))
            else:
                return redirect(url_for("verify_mfa"))

        except Exception as e:
            flash(f"Erreur technique : {e}", "danger")
            return redirect(url_for("force_reset_pwd"))

    return render_template("force_reset.html")


@app.route("/setup_mfa", methods=["GET", "POST"])
def setup_mfa():
    """
    Premiere configuration du MFA, affichee uniquement si l'utilisateur
    n'a pas encore de totp_secret enregistre. On genere un secret
    temporaire qu'on garde en session tant qu'il n'est pas confirme :
    si l'utilisateur ferme l'onglet sans valider, rien n'est ecrit en
    base et il devra recommencer proprement a la prochaine connexion
    """
    if 'pre_auth_user' not in session:
        return redirect(url_for("login"))

    username = session['pre_auth_user']

    if request.method == "POST":
        token = request.form.get("token")
        secret = session.get('temp_mfa_secret')

        totp = pyotp.TOTP(secret)
        if totp.verify(token):
            # Le code entre correspond bien au secret : on peut
            # considerer que l'appli Authenticator est correctement
            # configuree et on ecrit le secret definitivement
            save_user_totp_secret(username, secret)

            session.permanent = True
            session["user"] = username
            session["role"] = session.get('pre_auth_role')
            session["uuid"] = session.get('pre_auth_uuid')

            session.pop('pre_auth_user', None)
            session.pop('temp_mfa_secret', None)

            flash("MFA configure avec succes ! Bienvenue sur le SOC.", "success")
            return redirect(url_for("index"))
        else:
            flash("Code incorrect. Veuillez verifier l'application.", "danger")

    # Sur un GET (ou apres un echec de code), on garde le meme secret
    # tant qu'il existe deja en session, plutot que d'en regenerer un
    # nouveau a chaque affichage - sinon le QR code changerait a chaque
    # rechargement de page et l'utilisateur ne pourrait jamais scanner
    if 'temp_mfa_secret' not in session:
        session['temp_mfa_secret'] = pyotp.random_base32()

    secret = session['temp_mfa_secret']

    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name="CyberMonitors SOC"
    )

    # On genere le QR code directement en memoire (BytesIO) plutot que
    # de l'ecrire sur le disque, pas besoin de gerer un fichier temporaire
    # pour quelque chose qui ne sert qu'une fois
    img = qrcode.make(totp_uri)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    return render_template("setup_mfa.html", qr_code=qr_b64, secret=secret)


@app.route("/verify_mfa", methods=["GET", "POST"])
def verify_mfa():
    """
    Etape de MFA pour les connexions suivantes, une fois que le compte
    a deja un totp_secret enregistre. Contrairement a setup_mfa, ici on
    va lire le secret depuis la base, pas depuis la session
    """
    if 'pre_auth_user' not in session:
        return redirect(url_for("login"))

    username = session['pre_auth_user']

    if request.method == "POST":
        token = request.form.get("token")

        with open(JSON_PATH, "r") as f:
            accounts = json.load(f)
        secret = accounts.get(username, {}).get("totp_secret")

        if not secret:
            flash("Erreur fatale MFA.", "danger")
            return redirect(url_for("login"))

        totp = pyotp.TOTP(secret)
        if totp.verify(token):
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
    """Vide completement la session. Simple mais efficace, pas besoin de plus"""
    session.clear()
    return redirect(url_for("login"))


# ========================================================
# 4. ROUTES STANDARD DU DASHBOARD
# ========================================================

@app.route("/")
@login_required
def index():
    """
    Page d'accueil : verifie s'il y a des crises en cours sur le parc
    (et remonte un flash par crise), puis regenere les graphiques de
    comparaison globale avant de les afficher. La generation des graphes
    est faite a chaque chargement de page, donc si le dossier de sortie
    n'est pas accessible ou que le module plante, on ne bloque pas
    l'affichage pour autant (juste un print en log)
    """
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
    """
    Page de detail d'une machine. Deux niveaux de controle avant
    d'afficher quoi que ce soit :
    1) la machine demandee existe bien dans le parc (sinon 404, ca n'a
       pas de sens de dire "acces refuse" a une machine qui n'existe pas)
    2) elle fait bien partie du perimetre assigne a l'utilisateur
       connecte (sinon on refuse, meme si l'URL est tapee a la main)
    On ne fait jamais confiance uniquement au menu de navigation qui
    masque deja les machines hors perimetre cote HTML - un utilisateur
    un peu curieux peut toujours changer l'URL directement
    """
    if name not in PARC_INFORMATIQUE:
        abort(404)

    try:
        with open(JSON_PATH, "r") as f:
            accounts = json.load(f)
    except Exception:
        flash("Erreur systeme : Impossible de verifier vos autorisations.", "danger")
        return redirect(url_for("index"))

    user_data = accounts.get(session["user"], {})
    # Par defaut (compte sans assigned_assets defini, typiquement admin
    # ou monitor), on considere que l'utilisateur voit tout le parc
    user_assets = user_data.get("assigned_assets", PARC_INFORMATIQUE)

    if name not in user_assets:
        flash("Acces Refuse : Cet equipement n'est pas dans votre perimetre d'autorisation.", "danger")
        return redirect(url_for("index"))

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
            "status": get_container_status(name)
        }
    except Exception as e:
        print(f"Erreur lors du traitement de l'asset {name}: {e}")
        abort(500)

    return render_template("asset.html", asset=data)


@app.route("/profil")
@login_required
def profil():
    """
    Page de profil : on lit les infos depuis le fichier JSON.
    Grace a la fonction decrypt_val, les donnees chiffrees (nom, prenom, email, etc.)
    redeviennent lisibles pour l'utilisateur.
    """
    try:
        with open(JSON_PATH, "r") as f:
            accounts = json.load(f)
        user_info = accounts.get(session["user"], {})
    except Exception:
        user_info = {}

    # On utilise decrypt_val pour chaque champ sensible
    data = {
        "username": session["user"],
        "role": session.get("role", "user"),
        "uuid": user_info.get("id", "Non defini"),
        "blocked": user_info.get("blocked", False),
        "force_reset": user_info.get("force_reset", False),
        # On dechiffre les donnees privees pour l'affichage
        "nom": decrypt_val(user_info.get("nom", "Non renseigne")),
        "prenom": decrypt_val(user_info.get("prenom", "Non renseigne")),
        "email": decrypt_val(user_info.get("email", "Non renseigne")),
        "phone": decrypt_val(user_info.get("phone", "Non renseigne")),
        "entreprise": decrypt_val(user_info.get("entreprise", "Non renseigne")),
        "secteur": decrypt_val(user_info.get("secteur", "Non renseigne")),
        "poste": decrypt_val(user_info.get("poste", "Non renseigne"))
    }
    return render_template("profil.html", user_data=data)

# ========================================================
# 5. GESTION DES COMPTES (IAM)
# ========================================================

def generate_username(prenom, nom, role, accounts):
    """
    Convention de nommage maison : premiere lettre du prenom + le nom,
    avec un suffixe qui indique le role (-adm / -soc / -usr). Ca donne
    par exemple j.dupont-usr pour un compte utilisateur metier. On
    passe par unicodedata pour virer les accents (Jerome -> jerome et
    pas j\xe9r\xf4me), sinon on se retrouve avec des identifiants
    illisibles ou incompatibles avec certains outils systeme

    En cas de doublon (deux Jean Dupont dans la meme boite, ca arrive),
    on ajoute juste un chiffre a la fin
    """
    p = unicodedata.normalize('NFD', prenom).encode('ascii', 'ignore').decode('utf-8').lower()
    n = unicodedata.normalize('NFD', nom).encode('ascii', 'ignore').decode('utf-8').lower()

    suffix = "-adm" if role == "admin" else "-soc" if role == "monitor" else "-usr"
    base_username = f"{p[0]}.{n}{suffix}"

    final_username = base_username
    counter = 2
    while final_username in accounts:
        final_username = f"{base_username}{counter}"
        counter += 1

    return final_username


def generate_strong_password(length=PASSWORD_MIN_LENGTH):
    """
    Genere un mot de passe temporaire aleatoire pour les nouveaux
    comptes. On utilise secrets.choice() et pas random.choice(), c'est
    important : random n'est pas concu pour etre imprevisible dans un
    contexte de securite, secrets si.

    La boucle while est un peu bourrin mais efficace : on tire un mot de
    passe au hasard et on le garde seulement s'il coche toutes les
    cases de la politique de complexite (maj, min, au moins 3 chiffres,
    un symbole). Vu la taille de l'alphabet utilise, ca converge en
    general en une poignee d'essais
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = ''.join(secrets.choice(alphabet) for i in range(length))
        if (any(c.islower() for c in pwd) and any(c.isupper() for c in pwd)
                and sum(c.isdigit() for c in pwd) >= 3 and any(c in "!@#$%^&*" for c in pwd)):
            return pwd


@app.route("/create_account", methods=["GET", "POST"])
@login_required
def create_account():
    """
    Formulaire de creation de compte.
    On ajoute maintenant le chiffrement Fernet sur les données sensibles
    pour respecter la structure attendue par le script d'initialisation.
    """
    creator_role = session.get("role")
    if creator_role not in ["admin", "monitor"]:
        flash("Acces refuse : Seuls les administrateurs et analystes peuvent creer des comptes.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        prenom = request.form.get("prenom").strip()
        nom = request.form.get("nom").strip()
        email = request.form.get("email").strip()
        phone = request.form.get("phone", "").strip()
        entreprise = request.form.get("entreprise", "CyberMonitors").strip()
        secteur = request.form.get("secteur", "IT Security").strip()
        poste = request.form.get("poste", "Administrateur Systeme").strip()
        new_role = request.form.get("new_role").strip().lower()
        assigned_assets = request.form.getlist("assets")

        if creator_role == "monitor" and new_role == "admin":
            flash("Erreur d'elevation : Vous n'avez pas l'autorisation de creer un compte Administrateur.", "danger")
            return redirect(url_for("create_account"))

        if new_role == "user" and not assigned_assets:
            flash("Un compte 'Utilisateur Metier' doit avoir au moins un equipement assigne.", "danger")
            return redirect(url_for("create_account"))

        try:
            with open(JSON_PATH, "r") as f:
                accounts = json.load(f)
        except Exception:
            flash("Erreur fatale : Base de donnees JSON introuvable.", "danger")
            return redirect(url_for("index"))

        new_username = generate_username(prenom, nom, new_role, accounts)
        temp_password = generate_strong_password()
        hashed_password = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Si le rôle n'est pas 'user', il a accès à tout par défaut
        if new_role != "user":
            assigned_assets = PARC_INFORMATIQUE

        # Utilisation du chiffrement Fernet pour les donnees personnelles (PII)
        # On utilise une fonction lambda pour alleger le code
        enc = lambda val: cipher.encrypt(val.encode('utf-8')).decode('utf-8') if cipher else val

        new_user_data = {
            "id": str(uuid.uuid4()),
            "email": enc(email),
            "nom": enc(nom),
            "prenom": enc(prenom),
            "phone": enc(phone),
            "entreprise": enc(entreprise),
            "secteur": enc(secteur),
            "poste": enc(poste),
            "password": hashed_password,
            "role": new_role,
            "assigned_assets": assigned_assets,
            "blocked": False,
            "force_reset": True,
            "reset_by_admin": False,
            "totp_secret": None
        }

        accounts[new_username] = new_user_data

        try:
            with open(JSON_PATH, "w") as f:
                json.dump(accounts, f, indent=4)

            # Mise a jour du hash de signature apres modification
            if cipher:
                with open(JSON_PATH, 'rb') as f:
                    data = f.read()
                    # On recalcule le HMAC avec la cle Fernet pour que le script du binome reste content
                    signature = hmac.new(FERNET_KEY.encode('utf-8'), data, hashlib.sha256).hexdigest()
                    with open(os.path.join(os.path.dirname(JSON_PATH), ".users_docker.hmac"), 'w') as h:
                        h.write(signature)

            from alertes.envoie_mail import send_email
            sujet = "Bienvenue sur le SOC CyberMonitors - Vos identifiants"
            corps = f"""
            Bonjour {prenom},

            Votre compte d'acces a la plateforme CyberMonitors a ete provisionne.

            Identifiant : {new_username}
            Mot de passe temporaire : {temp_password}

            Lors de votre premiere connexion, il vous sera demande de modifier ce mot de passe ({PASSWORD_MIN_LENGTH} caracteres minimum) et de configurer votre application MFA (Google Authenticator).

            Cordialement,
            L'equipe SOC
            """
            send_email(email, sujet, corps)

            flash(f"Compte '{new_username}' provisionne.", "success")
        except Exception as e:
            flash(f"Erreur technique lors de la creation : {e}", "danger")

        return redirect(url_for("create_account"))

    return render_template("create_account.html", creator_role=creator_role, parc=PARC_INFORMATIQUE)


# ========================================================
# 6. ORCHESTRATION DOCKER (actions sur le parc)
# ========================================================

def est_isole(container):
    """Un conteneur est considere isole quand il n'a plus aucune interface reseau attachee"""
    networks = container.attrs['NetworkSettings']['Networks']
    return len(networks) == 0


@app.route("/api/machine/action", methods=["POST"])
@login_required
@admin_required
def machine_action():
    """
    Point d'entree unique pour toutes les actions Docker declenchees
    depuis le dashboard : demarrer, arreter, redemarrer, isoler,
    reconnecter. Avant d'executer quoi que ce soit, on relit l'etat
    reel du conteneur et on verifie que l'action demandee a bien un
    sens dans cet etat (par exemple, impossible d'isoler une machine
    deja eteinte). Le formulaire cote client desactive deja les
    boutons qui n'ont pas de sens, mais on ne se fie jamais uniquement
    a ca : rien n'empeche quelqu'un d'envoyer la requete directement
    """
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
        container.reload()

        etat_actuel = "stopped" if container.status != "running" else (
            "isolated" if est_isole(container) else "running"
        )

        if action == "start" and etat_actuel != "stopped":
            flash(f"{machine_name} est deja allume.", "warning")
            return redirect(request.referrer or url_for("index"))

        if action == "stop" and etat_actuel == "stopped":
            flash(f"{machine_name} est deja eteint.", "warning")
            return redirect(request.referrer or url_for("index"))

        if action == "isolate" and etat_actuel != "running":
            flash(f"Action impossible : {machine_name} doit etre allume et connecte pour etre isole.", "warning")
            return redirect(request.referrer or url_for("index"))

        if action == "reconnect" and etat_actuel != "isolated":
            flash(f"{machine_name} n'est pas isole, rien a reconnecter.", "warning")
            return redirect(request.referrer or url_for("index"))

        if action == "start":
            container.start()
            flash(f"[Docker] Conteneur {machine_name} demarre avec succes.", "success")

        elif action == "stop":
            container.stop()
            flash(f"[Docker] Conteneur {machine_name} arrete proprement.", "warning")

        elif action == "restart":
            container.restart()
            flash(f"[Docker] Conteneur {machine_name} redemarre.", "info")

        elif action == "isolate":
            # On deconnecte le conteneur de tous ses reseaux d'un coup,
            # au cas ou il en aurait plusieurs (en pratique il n'y en a
            # qu'un seul chez nous, mais autant etre generique)
            networks = container.attrs['NetworkSettings']['Networks']
            for net_name in networks:
                network = docker_client.networks.get(net_name)
                network.disconnect(container, force=True)
            container.reload()
            if est_isole(container):
                flash(f"[URGENCE SOC] {machine_name} isole. Coupure reseau confirmee (Containment).", "danger")
            else:
                flash(f"Echec de l'isolement de {machine_name}, reseau encore actif.", "danger")

        elif action == "reconnect":
            nom_reseau = get_target_network_name()
            print(f"[DEBUG reconnect] Tentative de connexion de {nom_conteneur} au reseau '{nom_reseau}'")
            network = docker_client.networks.get(nom_reseau)
            network.connect(container)
            container.reload()
            if est_isole(container):
                flash(f"Echec : {machine_name} semble toujours isole apres tentative de reconnexion.", "danger")
            else:
                flash(f"[Docker] {machine_name} reconnecte au reseau '{nom_reseau}'.", "success")

    except docker.errors.NotFound as e:
        flash(f"Erreur : conteneur ou reseau '{nom_conteneur}' introuvable ({e}).", "danger")
    except docker.errors.APIError as e:
        flash(f"Erreur de permissions Docker : {str(e)}", "danger")
    except Exception as e:
        print(f"Erreur d'orchestration Docker : {e}")
        flash("Erreur technique lors de l'execution de l'action.", "danger")

    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)