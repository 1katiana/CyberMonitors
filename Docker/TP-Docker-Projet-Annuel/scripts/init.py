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
import smtplib
from email.mime.text import MIMEText
from cryptography.fernet import Fernet
import uuid
import builtins

# --- VERROU DE SECURITE ANTI-BYPASS (CTRL+Z / CTRL+C / CTRL+D) ---
original_input = builtins.input
def secure_input(prompt=""):
    try:
        res = original_input(prompt)
        if '\x1a' in res or '\x03' in res or '\x04' in res: 
            print(f"\n\033[91m[!] Interruption (Ctrl) detectee. Arret de securite immediat.\033[0m")
            sys.exit(1)
        return res
    except (EOFError, KeyboardInterrupt):
        print(f"\n\033[91m[!] Interruption detectee. Arret de securite immediat.\033[0m")
        sys.exit(1)

builtins.input = secure_input

original_getpass = getpass.getpass
def secure_getpass(prompt=""):
    try:
        res = original_getpass(prompt)
        if '\x1a' in res or '\x03' in res or '\x04' in res:
            print(f"\n\033[91m[!] Interruption (Ctrl) detectee. Arret de securite immediat.\033[0m")
            sys.exit(1)
        return res
    except (EOFError, KeyboardInterrupt):
        print(f"\n\033[91m[!] Interruption detectee. Arret de securite immediat.\033[0m")
        sys.exit(1)

getpass.getpass = secure_getpass
# --------------------------------------------------------

# - CONFIGURATION -
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
INIT_STATE_FILE = os.path.join(DATA_DIR, ".init_step")

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
    if len(pwd) < 12 : missing.append("12 caracteres minimum")
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

        if os.path.exists(ENV_PATH):
            found_env = ENV_PATH
            
        for root, dirs, files in os.walk(DATA_DIR):
            for f in files:
                name_lower = f.lower()
                if not found_env and name_lower in ['.env', 'env.txt', '.env.txt']: 
                    found_env = os.path.join(root, f)
                elif name_lower in ['users_docker.json', 'users_docker.json.txt']: 
                    found_json = os.path.join(root, f)

        missing_files = False
        if not found_env:
            print(f"{C_DANGER}[!] Fichier .env introuvable.{C_END}")
            missing_files = True
        if not found_json:
            print(f"{C_DANGER}[!] Fichier users_docker.json introuvable.{C_END}")
            missing_files = True

        if missing_files:
            input("\nAppuyez sur Entree pour reessayer...")
            continue

        # --- VERIFICATION DE L'INTEGRITE DU JSON ---
        try:
            with open(found_json, 'r') as f: json.load(f)
        except json.JSONDecodeError:
            print(f"{C_DANGER}[!] Le fichier users_docker.json est corrompu ou mal formate.{C_END}")
            input("\nAppuyez sur Entree pour reessayer...")
            continue

        # --- VERIFICATION STRICTE DU CONTENU DU .ENV ---
        required_keys = ["EMAIL_USER", "EMAIL_PASSWORD", "EMAIL_HOST", "EMAIL_PORT", "FLASK_SECRET_KEY", "FERNET_SECRET_KEY"]
        imported_env_vars = {}
        
        with open(found_env, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    imported_env_vars[k.strip()] = v.strip()
        
        missing_keys = [key for key in required_keys if not imported_env_vars.get(key)]
        
        if missing_keys:
            print(f"{C_DANGER}[!] Import invalide : Le fichier .env est incomplet.{C_END}")
            print(f"{C_WARN}Les valeurs suivantes sont manquantes ou vides : {', '.join(missing_keys)}{C_END}")
            input("\nAppuyez sur Entree pour reessayer...")
            continue

        # --- VERIFICATION DE LA CLEF FERNET (COMPATIBILITE BDD) ---
        db_action = "RESTORE_ALL" 

        while True:
            fernet_key_test = imported_env_vars.get("FERNET_SECRET_KEY", "")
            is_key_valid = False
            try:
                cipher = Fernet(fernet_key_test.encode('utf-8'))
                with open(found_json, 'r') as f:
                    test_data = json.load(f)
                
                # S'il y a des utilisateurs, on teste le dechiffrement reel d'une donnee
                if test_data:
                    first_u = list(test_data.keys())[0]
                    test_val = test_data[first_u].get("nom", "")
                    if test_val and test_val != "Non renseigne":
                        cipher.decrypt(test_val.encode('utf-8'))
                is_key_valid = True
            except Exception:
                is_key_valid = False
                
            if is_key_valid:
                break
                
            print(f"\n{C_DANGER}[!] ERREUR DE CHIFFREMENT DETECTEE{C_END}")
            print(f"{C_WARN}La clef FERNET du .env ne peut pas dechiffrer la base users_docker.json importee !{C_END}")
            print("1. Saisir la bonne clef FERNET_SECRET_KEY manuellement")
            print("2. Conserver les identifiants mail du .env, mais recreer un compte Admin vierge")
            print("0. Annuler la restauration")
            
            c_err = input("Choix (0-2) : ").strip()
            if c_err == '0':
                return "BACK"
            elif c_err == '1':
                new_k = input(f"{C_BASE}Nouvelle clef FERNET : {C_END}").strip()
                imported_env_vars["FERNET_SECRET_KEY"] = new_k
            elif c_err == '2':
                db_action = "RECREATE_DB"
                break
            else:
                print(f"{C_DANGER}Choix invalide.{C_END}")

        # --- VERIFICATION PAR ENVOI DE CODE (Tests des Mails Importes) ---
        print(f"\n{C_BASE}[*] Verification des identifiants mail importes...{C_END}")

        mail = imported_env_vars['EMAIL_USER']
        host = imported_env_vars['EMAIL_HOST']
        port = int(imported_env_vars['EMAIL_PORT'])
        pwd_app = imported_env_vars['EMAIL_PASSWORD']

        expected_code = str(secrets.randbelow(900000) + 100000)
        msg = MIMEText(f"Bonjour,\n\nVoici votre code de verification pour valider la restauration de CyberMonitors : {expected_code}\n\nSi vous n'avez pas demande ce code, ignorez cet email.")
        msg['Subject'] = 'Code de verification - Restauration CyberMonitors'
        msg['From'] = mail
        msg['To'] = mail

        success = False
        error_msg = ""
        
        try:
            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                    server.login(mail, pwd_app)
                    server.sendmail(mail, [mail], msg.as_string())
            else:
                with smtplib.SMTP(host, port, timeout=10) as server:
                    server.starttls()
                    server.login(mail, pwd_app)
                    server.sendmail(mail, [mail], msg.as_string())
            success = True
        except Exception as e:
            error_msg = str(e)

        if not success:
            print(f"{C_DANGER}[!] Echec de l'envoi de l'email avec les identifiants importes.{C_END}")
            print(f"{C_WARN}Details : {error_msg}{C_END}")
            print(f"{C_DANGER}Votre fichier .env est obselete ou invalide. Les identifiants email ne fonctionnent plus.{C_END}")
            input("\nAppuyez sur Entree pour reessayer...")
            continue
            
        print(f"{C_OK}[+] Email envoye avec succes a {mail}.{C_END}")
        attempts = 3
        code_validated = False
        
        while attempts > 0:
            user_code = input(f"\n{C_WARN}Entrez le code a 6 chiffres recu (ou '0' pour annuler) : {C_END}").strip()
            
            if user_code == '0':
                print(f"{C_DANGER}[!] Restauration annulee.{C_END}")
                break
            
            if user_code == expected_code:
                print(f"{C_OK}[+] Verification reussie ! Les identifiants importes sont valides.{C_END}")
                code_validated = True
                break
            else:
                attempts -= 1
                if attempts > 0:
                    print(f"{C_DANGER}[!] Code incorrect. Il vous reste {attempts} essai(s).{C_END}")
                else:
                    print(f"{C_DANGER}[!] Echecs trop nombreux. La restauration est annulee.{C_END}")
        
        if not code_validated:
            continue

        # --- SAUVEGARDE FINALE DES FICHIERS ---
        with open(ENV_PATH, 'w') as f:
            for k, v in imported_env_vars.items():
                f.write(f"{k}={v}\n")

        if db_action == "RESTORE_ALL":
            if found_json != JSON_PATH:
                shutil.copy(found_json, JSON_PATH)
            with open(INIT_STATE_FILE, 'w') as f:
                f.write("MANUAL_IMPORT")
            print(f"\n{C_OK}[+] Fichiers importes, controles et valides avec succes.{C_END}")
            time.sleep(2)
            return "OK"
        else:
            print(f"\n{C_WARN}[!] .env valide. La base de donnees doit etre recreee.{C_END}")
            time.sleep(2)
            return "RECREATE_DB"

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

    etape = 1
    env_vars = {}
    fernet_key = ""
    admin_user = ""
    hashed_pwd = ""
    mode = ""
    
    nom, prenom, email_in, phone_in = "", "", "", ""
    entreprise, secteur, poste = "", "", ""

    if os.path.exists(INIT_STATE_FILE):
        with open(INIT_STATE_FILE, 'r') as f:
            saved_step = f.read().strip()
        if saved_step == "MANUAL_IMPORT":
            print(f"{C_WARN}[*] Reprise de l'installation detectee (Import manuel)...{C_END}")
            mode = '2'
            etape = 6
            if os.path.exists(ENV_PATH):
                with open(ENV_PATH, 'r') as f:
                    for line in f:
                        if line.startswith('FERNET_SECRET_KEY='):
                            fernet_key = line.split('=', 1)[1].strip()
            time.sleep(2)

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
                    etape = 6 
                elif res == "RECREATE_DB":
                    with open(ENV_PATH, 'r') as f:
                        for line in f:
                            if line.startswith('FERNET_SECRET_KEY='):
                                fernet_key = line.split('=', 1)[1].strip()
                    etape = 4
            elif mode == '1':
                etape = 2
            else:
                print(f"{C_DANGER}Choix invalide.{C_END}")
                time.sleep(1)

        elif etape == 2:
            clear_screen()
            print(f"{C_BASE}=== ETAPE 1 : CONFIGURATION EMAIL ==={C_END}")
            print(f"{C_WARN}La configuration d'une adresse email est OBLIGATOIRE pour le monitoring.{C_END}")
            print("Service mail utilise pour les alertes (Tapez 0 pour revenir) :")
            print("1. Google (Gmail)   2. Microsoft (Outlook/Hotmail)   3. Autre (SMTP)")
            choix = input("Choix (1-3) : ").strip()

            if choix == '0': etape = 1; continue
            if choix not in ['1', '2', '3']: continue

            while True:
                mail = input(f"\n{C_BASE}Adresse e-mail complete (0 pour retour) : {C_END}").strip()
                if mail == '0': break
                
                parts = mail.split('@')
                if len(parts) != 2 or not parts[0] or not parts[1] or "." not in parts[1]:
                    print(f"{C_DANGER}Format d'e-mail invalide (ex: nom@domaine.com).{C_END}")
                    continue
                    
                domain = "@" + parts[1].lower()
                
                if choix == '1' and domain not in ['@gmail.com', '@googlemail.com']:
                    print(f"{C_DANGER}[!] Choix Google invalide : L'adresse doit finir par @gmail.com{C_END}")
                    continue
                    
                if choix == '2' and not any(domain.startswith(d) for d in ['@outlook.', '@hotmail.', '@live.', '@msn.']):
                    print(f"{C_DANGER}[!] Choix Microsoft invalide : L'adresse doit etre @outlook, @hotmail, etc.{C_END}")
                    continue
                    
                env_vars['EMAIL_USER'] = mail
                break
                
            if mail == '0': continue

            if choix == '1':
                print(f"\n{C_WARN}[GUIDE GOOGLE] 1. Securite > Valide en 2 etapes > Mots de passe des applications.{C_END}")
            elif choix == '2':
                print(f"\n{C_WARN}[GUIDE MS] Securite > Options avancees > Mots de passe d'application.{C_END}")
            else:
                print(f"\n{C_WARN}[SMTP] Assurez-vous que votre fournisseur autorise les mots de passe d'application.{C_END}")

            while True:
                pwd = input(f"{C_BASE}Mot de passe d'application (0 pour retour) : {C_END}").replace(" ", "").strip()
                if pwd == '0': break
                
                if choix == '1':
                    if len(pwd) == 16 and pwd.isalpha():
                        env_vars['EMAIL_PASSWORD'] = pwd
                        break
                    else:
                        print(f"{C_DANGER}[!] Invalide. Un mot de passe d'app Google fait 16 lettres (sans espaces ni chiffres).{C_END}")
                else:
                    if len(pwd) >= 8:
                        env_vars['EMAIL_PASSWORD'] = pwd
                        break
                    else:
                        print(f"{C_DANGER}[!] Saisie invalide ou mot de passe trop court.{C_END}")
            
            if pwd == '0': continue

            # --- VERIFICATION PAR ENVOI DE CODE ---
            if choix == '3':
                while True:
                    smtp_host = input(f"\n{C_BASE}Serveur SMTP (ex: smtp.mail.yahoo.com) (0 pour retour) : {C_END}").strip()
                    if smtp_host == '0': break
                    smtp_port_str = input(f"{C_BASE}Port SMTP (465 ou 587) (0 pour retour) : {C_END}").strip()
                    if smtp_port_str == '0': break
                    
                    if smtp_port_str in ['465', '587']:
                        smtp_port = int(smtp_port_str)
                        break
                    print(f"{C_DANGER}Port non supporte. Utilisez 465 (SSL) ou 587 (TLS).{C_END}")
                
                if smtp_host == '0' or smtp_port_str == '0': continue
                env_vars['EMAIL_HOST'] = smtp_host
                env_vars['EMAIL_PORT'] = str(smtp_port)
            else:
                env_vars['EMAIL_HOST'] = "smtp.gmail.com" if choix == '1' else "smtp-mail.outlook.com"
                env_vars['EMAIL_PORT'] = "465" if choix == '1' else "587"

            print(f"\n{C_BASE}[*] Tentative de connexion et envoi du code de verification...{C_END}")
            
            expected_code = str(secrets.randbelow(900000) + 100000)
            msg = MIMEText(f"Bonjour,\n\nVoici votre code de verification pour initialiser CyberMonitors : {expected_code}\n\nSi vous n'avez pas demande ce code, ignorez cet email.")
            msg['Subject'] = 'Code de verification CyberMonitors'
            msg['From'] = mail
            msg['To'] = mail

            success = False
            error_msg = ""
            
            try:
                host = env_vars['EMAIL_HOST']
                port = int(env_vars['EMAIL_PORT'])
                pwd_app = env_vars['EMAIL_PASSWORD']
                
                if port == 465:
                    with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                        server.login(mail, pwd_app)
                        server.sendmail(mail, [mail], msg.as_string())
                else:
                    with smtplib.SMTP(host, port, timeout=10) as server:
                        server.starttls()
                        server.login(mail, pwd_app)
                        server.sendmail(mail, [mail], msg.as_string())
                success = True
            except Exception as e:
                error_msg = str(e)

            if success:
                print(f"{C_OK}[+] Email envoye avec succes a {mail}.{C_END}")
                attempts = 3
                code_validated = False
                
                while attempts > 0:
                    user_code = input(f"\n{C_WARN}Entrez le code a 6 chiffres recu (ou '0' si non recu/retour) : {C_END}").strip()
                    
                    if user_code == '0':
                        print(f"{C_DANGER}[!] Configuration annulee. Vous pouvez recommencer.{C_END}")
                        break
                    
                    if user_code == expected_code:
                        print(f"{C_OK}[+] Verification reussie ! Compte mail confirme et fonctionnel.{C_END}")
                        code_validated = True
                        break
                    else:
                        attempts -= 1
                        if attempts > 0:
                            print(f"{C_DANGER}[!] Code incorrect. Il vous reste {attempts} essai(s).{C_END}")
                        else:
                            print(f"{C_DANGER}[!] Echecs trop nombreux. L'etape est annulee.{C_END}")
                
                if not code_validated:
                    continue 
            else:
                print(f"{C_DANGER}[!] Echec de l'envoi de l'email.{C_END}")
                print(f"{C_WARN}Details de l'erreur : {error_msg}{C_END}")
                print(f"{C_DANGER}Verifiez votre mot de passe d'application ou que l'acces SMTP est bien autorise sur votre compte.{C_END}")
                input("Appuyez sur Entree pour reessayer...")
                continue
                
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
            if c1 == '2': 
                while True:
                    flask_k = input("Clef (minimum 16 caracteres) : ").strip()
                    if len(flask_k) >= 16:
                        env_vars['FLASK_SECRET_KEY'] = flask_k
                        break
                    print(f"{C_DANGER}La clef ne peut pas etre vide et doit faire au moins 16 caracteres.{C_END}")
            elif c1 == '1': 
                env_vars['FLASK_SECRET_KEY'] = secrets.token_hex(24)

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
                    if not k:
                        print(f"{C_DANGER}La clef ne peut pas etre vide.{C_END}")
                        continue
                    try:
                        Fernet(k.encode('utf-8'))
                        fernet_key = k
                        break
                    except: 
                        print(f"{C_DANGER}Cle invalide ou corrompue. Elle doit etre generable via Fernet.generate_key().{C_END}")
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
                pwd_master = getpass.getpass("Mot de passe (0 pour retour) : ").strip()
                if pwd_master == '0': break
                missing = check_password_complexity(pwd_master)
                if missing:
                    print(f"{C_DANGER}Manque : {', '.join(missing)}{C_END}")
                    continue
                confirm = getpass.getpass("Confirmez le mot de passe : ").strip()
                if pwd_master == confirm:
                    hashed_pwd = bcrypt.hashpw(pwd_master.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    break
                print(f"{C_DANGER}Correspondance echouee.{C_END}")
            if pwd_master == '0': continue
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
            if os.path.exists(INIT_STATE_FILE):
                os.remove(INIT_STATE_FILE)
                
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