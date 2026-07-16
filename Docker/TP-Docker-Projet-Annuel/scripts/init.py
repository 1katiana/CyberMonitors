import os
import sys
import json
import bcrypt
import getpass
import secrets
import hmac
import hashlib
import time
import string
import shutil
import subprocess
from cryptography.fernet import Fernet
import uuid

# --- CONFIGURATION ---
ROOT_DIR = "/infrastructure" if os.environ.get("IS_MASTER_CONSOLE") == "1" else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ENV_PATH = os.path.join(ROOT_DIR, "Docker", "TP-Docker-Projet-Annuel", ".env")
DATA_DIR = os.path.join(ROOT_DIR, "Data")
USERS_DIR = os.path.join(DATA_DIR, "Users")
BACKUPS_DIR = os.path.join(DATA_DIR, "backups")
LOGS_DIR = os.path.join(DATA_DIR, "Logs")
BACKUP_CONFIG_DIR = os.path.join(ROOT_DIR, "code_monitoring", "gestion de sauvegarde")
BACKUP_CONFIG_FILE = os.path.join(BACKUP_CONFIG_DIR, "backup_config.json")
JSON_PATH = os.path.join(USERS_DIR, "users_docker.json")
HMAC_SIGN_FILE = os.path.join(USERS_DIR, ".users_docker.hmac")
SHADOW_BACKUP = os.path.join(USERS_DIR, ".users_docker.shadow.enc")
INIT_FLAG = os.path.join(DATA_DIR, ".initialized")

# *** DESIGN ***
C_BASE = '\033[96m'
C_OK = '\033[92m'
C_WARN = '\033[93m'
C_DANGER = '\033[91m'
C_END = '\033[0m'

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def check_password_complexity(pwd):
    missing = []
    if len(pwd) < 6: missing.append("6 caracteres minimum")
    if not any(c.isupper() for c in pwd): missing.append("une majuscule")
    if not any(c.islower() for c in pwd): missing.append("une minuscule")
    if not any(c.isdigit() for c in pwd): missing.append("un chiffre")
    if not any(c in string.punctuation for c in pwd): missing.append("un symbole specifique (!@#$%^&*...)")
    return missing

def wake_up_infrastructure():
    print(f"\n{C_WARN}[*] REVEIL DU PARC INFORMATIQUE...{C_END}")
    containers = ["monitor_collector", "linux-srv-1", "linux-srv-2", "win-wkst-1", "win-wkst-2", "win-srv-indispensable"]
    subprocess.run(["docker", "start"] + containers, capture_output=True)
    print(f"{C_OK}[+] Les machines sont en ligne et fonctionnelles.{C_END}")

def setup_directories():
    for d in [DATA_DIR, USERS_DIR, BACKUPS_DIR, LOGS_DIR, BACKUP_CONFIG_DIR]:
        os.makedirs(d, exist_ok=True)

def attempt_auto_import():
    while True:
        clear_screen()
        print(f"{C_WARN}=== RESTAURATION INTELLIGENTE ==={C_END}")
        print(f"1. Placez votre ancien fichier {C_OK}users_docker.json{C_END} dans le dossier 'Data'.")
        print(f"2. Verifiez que votre ancien {C_OK}.env{C_END} est bien dans 'Docker/TP-Docker-Projet-Annuel/'.")
        print(f"(Tapez 0 pour revenir au menu precedent)\n")

        rep = input("Avez-vous depose les fichiers ? (oui/0) : ").strip().lower()
        if rep == '0': return "BACK"
        if rep != 'oui': continue

        print(f"\n{C_BASE}[*] Scan des fichiers de sauvegarde en cours...{C_END}")
        found_env, found_json = None, None

        # 1. On verifie si le .env est directement a sa bonne place
        if os.path.exists(ENV_PATH):
            found_env = ENV_PATH
            
        # 2. On scanne quand meme Data au cas ou
        for root, dirs, files in os.walk(DATA_DIR):
            for f in files:
                name_lower = f.lower()
                if not found_env and name_lower in ['.env', 'env.txt', '.env.txt']: 
                    found_env = os.path.join(root, f)
                elif name_lower in ['users_docker.json', 'users_docker.json.txt']: 
                    found_json = os.path.join(root, f)

        missing = False
        if not found_env:
            print(f"{C_DANGER}[!] Fichier .env introuvable.{C_END}")
            missing = True
        if not found_json:
            print(f"{C_DANGER}[!] Fichier users_docker.json introuvable.{C_END}")
            missing = True

        if missing:
            input("\nAppuyez sur Entree pour reessayer...")
            continue

        try:
            with open(found_json, 'r') as f: json.load(f)
        except json.JSONDecodeError:
            print(f"{C_DANGER}[!] Le fichier users_docker.json est corrompu ou mal formate.{C_END}")
            input("\nAppuyez sur Entree pour reessayer...")
            continue

        if found_env != ENV_PATH:
            shutil.copy(found_env, ENV_PATH)
        if found_json != JSON_PATH:
            shutil.copy(found_json, JSON_PATH)
            
        print(f"\n{C_OK}[+] Fichiers importes et valides avec succes.{C_END}")
        time.sleep(2)
        return "OK"

def configure_backup():
    clear_screen()
    print(f"{C_BASE}=== CONFIGURATION DES SAUVEGARDES ==={C_END}")
    print("Parametrez la sauvegarde automatique de la base de donnees. (Tapez 0 pour revenir)\n")

    mapping_temps = {"minutes": "minutes", "heures": "hours", "jours": "days"}

    while True:
        interval_fr = input("Unite de temps (minutes/heures/jours) : ").strip().lower()
        if interval_fr == '0': return "BACK"
        if interval_fr in mapping_temps:
            interval_type = mapping_temps[interval_fr]
            break
        print(f"{C_DANGER}Unite invalide. Veuillez taper minutes, heures ou jours.{C_END}")

    while True:
        val = input(f"Faire une sauvegarde toutes les X {interval_fr} (ex: 5) : ").strip()
        if val == '0': return "BACK"
        if val.isdigit() and int(val) > 0:
            interval_value = int(val)
            break
        print(f"{C_DANGER}Veuillez entrer un nombre entier positif.{C_END}")

    while True:
        val = input("Nombre maximum de sauvegardes a conserver (ex: 6) : ").strip()
        if val == '0': return "BACK"
        if val.isdigit() and int(val) > 0:
            retention = int(val)
            break
        print(f"{C_DANGER}Veuillez entrer un nombre entier positif.{C_END}")

    config = {
        "interval_type": interval_type,
        "interval_value": interval_value,
        "retention_count": retention
    }

    with open(BACKUP_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    print(f"{C_OK}[+] Configuration de sauvegarde terminee.{C_END}")
    time.sleep(1)
    return "OK"

def main():
    setup_directories()

    # Variables d'etat
    etape = 1
    env_vars = {}
    fernet_key = ""
    admin_user = ""
    hashed_pwd = ""
    mode = ""
    
    # Variables de profil par defaut
    nom, prenom, email_in, phone_in = "", "", "", ""
    entreprise, secteur, poste = "", "", ""

    while True:
        if etape == 1:
            clear_screen()
            print(f"{C_BASE}======================================================{C_END}")
            print(f"{C_BASE}    CYBER MONITOR : ASSISTANT DE PREMIER DEMARRAGE    {C_END}")
            print(f"{C_BASE}======================================================{C_END}\n")
            print("1. Installation a neuf (Nouvelle base et cles)")
            print("2. Restauration (J'ai mes anciens fichiers)\n")
            mode = input("Choix (1/2) (0 pour quitter) : ").strip()
            
            if mode == '0': sys.exit(0)
            elif mode == '2':
                res = attempt_auto_import()
                if res == "BACK": continue
                if res == "OK":
                    with open(ENV_PATH, 'r') as f:
                        for line in f:
                            if line.startswith('FERNET_SECRET_KEY='):
                                fernet_key = line.split('=', 1)[1].strip()
                    with open(JSON_PATH, 'rb') as f: data = f.read()
                    with open(HMAC_SIGN_FILE, 'w') as f: f.write(hmac.new(fernet_key.encode('utf-8'), data, hashlib.sha256).hexdigest())
                    etape = 6 # On saute a la config backup
            elif mode == '1':
                etape = 2
            else:
                print(f"{C_DANGER}Choix invalide.{C_END}")
                time.sleep(1)

        elif etape == 2:
            clear_screen()
            print(f"{C_BASE}=== ETAPE 1 : CONFIGURATION EMAIL ==={C_END}")
            print("Service mail utilise pour les alertes (Tapez 0 pour revenir) :")
            print("1. Google   2. Microsoft   3. Passer")
            choix = input("Choix (1-3) : ").strip()

            if choix == '0': etape = 1; continue
            if choix not in ['1', '2', '3']: continue

            if choix != '3':
                pwd = input(f"\n{C_BASE}Collez votre mot de passe d'application ici (ou 0 pour revenir) : {C_END}").replace(" ", "").strip()
                if pwd == '0': continue
                env_vars['EMAIL_PASSWORD'] = pwd
            else:
                env_vars['EMAIL_PASSWORD'] = ""
            etape = 3

        elif etape == 3:
            clear_screen()
            print(f"{C_BASE}=== ETAPE 2 : SECURITE DES CLES ==={C_END}")
            while True:
                print("\nCle FLASK_SECRET_KEY : 1. Auto  2. Manuelle  0. Retour")
                c1 = input("Choix : ").strip()
                if c1 in ['0', '1', '2']: break
                print(f"{C_DANGER}Saisie invalide.{C_END}")

            if c1 == '0': etape = 2; continue
            if c1 == '2': env_vars['FLASK_SECRET_KEY'] = input("Clef : ").strip()
            elif c1 == '1': env_vars['FLASK_SECRET_KEY'] = secrets.token_hex(24)

            while True:
                print("\nCle FERNET_SECRET_KEY : 1. Auto  2. Manuelle  0. Retour")
                c2 = input("Choix : ").strip()
                if c2 in ['0', '1', '2']: break
                print(f"{C_DANGER}Saisie invalide.{C_END}")

            if c2 == '0': continue
            if c2 == '2':
                while True:
                    k = input("Clef (ou 0 pour revenir) : ").strip()
                    if k == '0': break
                    try:
                        Fernet(k.encode('utf-8'))
                        fernet_key = k
                        break
                    except: print(f"{C_DANGER}Cle invalide ou corrompue.{C_END}")
                if k == '0': continue
            elif c2 == '1':
                fernet_key = Fernet.generate_key().decode('utf-8')

            env_vars['FERNET_SECRET_KEY'] = fernet_key
            with open(ENV_PATH, 'w') as f:
                for k, v in env_vars.items(): f.write(f"{k}={v}\n")
            etape = 4

        elif etape == 4:
            clear_screen()
            print(f"{C_WARN}=== ETAPE 3 : IDENTIFIANTS DU COMPTE MASTER ==={C_END}")
            admin_user = input("\nIdentifiant Master (ex: root) (0 pour retour) : ").strip().lower()
            if admin_user == '0': etape = 3; continue
            if not admin_user: continue

            while True:
                pwd = getpass.getpass("Mot de passe (0 pour retour) : ").strip()
                if pwd == '0': break
                missing = check_password_complexity(pwd)
                if missing:
                    print(f"{C_DANGER}Manque : {', '.join(missing)}{C_END}")
                    continue
                confirm = getpass.getpass("Confirmez le mot de passe : ").strip()
                if pwd == confirm:
                    hashed_pwd = bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    break
                print(f"{C_DANGER}Correspondance echouee.{C_END}")
            if pwd == '0': continue
            etape = 5

        elif etape == 5:
            clear_screen()
            print(f"{C_WARN}=== ETAPE 4 : PROFIL DU MASTER ADMIN ==={C_END}")
            print("Veuillez renseigner vos informations (Tapez 0 pour revenir en arriere).\n")
            
            nom = input("Nom de famille (0 pour retour) : ").strip()
            if nom == '0': etape = 4; continue
            
            prenom = input("Prenom (0 pour retour) : ").strip()
            if prenom == '0': etape = 4; continue
            
            email_in = input("Email (vide pour ignorer) : ").strip()
            phone_in = input("Telephone (vide pour ignorer) : ").strip()
            
            entreprise = input("Entreprise (vide = CyberMonitors) : ").strip()
            secteur = input("Secteur (vide = IT Security) : ").strip()
            poste = input("Poste (vide = Administrateur Systeme) : ").strip()

            # Application des valeurs par defaut
            if not entreprise: entreprise = "CyberMonitors"
            if not secteur: secteur = "IT Security"
            if not poste: poste = "Administrateur Systeme"
            if not email_in: email_in = "Non renseigne"
            if not phone_in: phone_in = "Non renseigne"

            cipher = Fernet(fernet_key.encode('utf-8'))
            def encrypt_val(val): return cipher.encrypt(val.encode('utf-8')).decode('utf-8')

            users_data = {
                admin_user: {
                    "id": str(uuid.uuid4()), 
                    "blocked": False, 
                    "password": hashed_pwd,
                    "role": "admin", 
                    "force_reset": False, 
                    "reset_by_admin": False,
                    "failed_attempts": 0,
                    "nom": encrypt_val(nom), 
                    "prenom": encrypt_val(prenom),
                    "email": encrypt_val(email_in), 
                    "phone": encrypt_val(phone_in),
                    "entreprise": encrypt_val(entreprise), 
                    "secteur": encrypt_val(secteur),
                    "poste": encrypt_val(poste)
                }
            }
            
            # L'ajout de 'indent=4' garantit un formatage vertical propre et lisible !
            with open(JSON_PATH, 'w') as f: 
                json.dump(users_data, f, indent=4)
                
            with open(JSON_PATH, 'rb') as f:
                with open(HMAC_SIGN_FILE, 'w') as h: 
                    h.write(hmac.new(fernet_key.encode('utf-8'), f.read(), hashlib.sha256).hexdigest())
                    
            with open(SHADOW_BACKUP, 'wb') as f: 
                f.write(cipher.encrypt(json.dumps(users_data, indent=4).encode('utf-8')))
            
            etape = 6

        elif etape == 6:
            if configure_backup() == "BACK":
                etape = 1 if mode == '2' else 5
                continue
            etape = 7

        elif etape == 7:
            # === DEBLOCAGE FINAL ===
            with open(INIT_FLAG, 'w') as f: f.write("DONE")
            wake_up_infrastructure()
            print(f"\n{C_OK}======================================================{C_END}")
            print(f"{C_OK}  INITIALISATION TERMINEE AVEC SUCCES !               {C_END}")
            print(f"{C_OK}======================================================{C_END}\n")
            print(f"{C_WARN}[!] Fin de session pour application des parametres...{C_END}")
            time.sleep(2)
            break

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(1)