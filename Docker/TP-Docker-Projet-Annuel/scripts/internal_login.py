import builtins
import getpass
import sys
import time
import os
import bcrypt
import pwd
import json
import subprocess
import string
import shutil
import signal
import logging
import sqlite3
import random
import hmac
import hashlib
import zipfile
import io
import glob
import smtplib
from email.mime.text import MIMEText
import secrets
from cryptography.fernet import Fernet

_orig_input = builtins.input
def safe_input(prompt=""):
    try:
        return _orig_input(prompt)
    except EOFError:
        print()
        return ""
builtins.input = safe_input

_orig_getpass = getpass.getpass
def safe_getpass(prompt=""):
    try:
        return _orig_getpass(prompt)
    except EOFError:
        print()
        return ""
getpass.getpass = safe_getpass

SEUIL_CRITIQUE = 10       
SEUIL_AVERTISSEMENT = 3   

MACHINE_NAME = os.environ.get("MACHINE_NAME", "UNKNOWN_MACHINE")
LOG_DIR = "/app/Data/Logs"
os.makedirs(LOG_DIR, exist_ok=True)
CONSOLE_LOCK_FILE = os.path.join(LOG_DIR, f".console_lock_{MACHINE_NAME}")
HMAC_SIGN_FILE = "/app/Data/Users/.users_docker.hmac"
SHADOW_BACKUP = "/app/Data/Users/.users_docker.shadow.enc"
BACKUP_DATA_DIR = "/app/Data/backups"

logging.basicConfig(
    filename=os.path.join(LOG_DIR, f"{MACHINE_NAME}_security.log"),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def log_security_event(username, event_type, severity, details):
    log_msg = f"User: {username} | Event: {event_type} | Details: {details}"
    if severity == "CRITICAL": logging.critical(log_msg)
    elif severity == "WARNING": logging.warning(log_msg)
    else: logging.info(log_msg)

    db_path = "/app/Data/monitoring.db"
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO security_events (machine_name, username, event_type, severity, details)
            VALUES (?, ?, ?, ?, ?)
        """, (MACHINE_NAME, username, event_type, severity, details))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Erreur d'insertion SQL : {e}")

def get_console_lock():
    if os.path.exists(CONSOLE_LOCK_FILE):
        try:
            with open(CONSOLE_LOCK_FILE, 'r') as f:
                return float(f.read().strip())
        except: pass
    return 0

def set_console_lock(lock_until):
    try:
        with open(CONSOLE_LOCK_FILE, 'w') as f:
            f.write(str(lock_until))
    except: pass

C_OK = '\033[92m'
C_DANGER = '\033[91m'
C_WARN = '\033[93m'
C_BASE = '\033[96m'
C_END = '\033[0m'

def get_cipher():
    env_key = os.getenv("FERNET_SECRET_KEY")
    if not env_key:
        try:
            out = subprocess.check_output(
                ["docker", "exec", "monitor_dashboard", "cat", "/infrastructure/Docker/TP-Docker-Projet-Annuel/.env"], 
                stderr=subprocess.DEVNULL
            ).decode('utf-8')
            for line in out.splitlines():
                if line.strip().startswith('FERNET_SECRET_KEY='):
                    env_key = line.split('=', 1)[1].strip()
                    break
        except Exception:
            pass

    if not env_key:
        print(f"\n{C_DANGER}[!] ERREUR FATALE SYSTEME : Clef FERNET_SECRET_KEY introuvable !{C_END}")
        log_security_event("SYSTEM", "MISSING_ENV_KEY", "CRITICAL", "Fichier .env ou clef de chiffrement absente")
        time.sleep(4)
        sys.exit(1)
        
    try: 
        return Fernet(env_key.encode('utf-8'))
    except Exception as e:
        print(f"\n{C_DANGER}[!] ERREUR FATALE SYSTEME : Clef de chiffrement invalide ou corrompue.{C_END}")
        sys.exit(1)

def decrypt_val(val, cipher):
    if not val or val == "Non renseigne": return "Non renseigne"
    try: return cipher.decrypt(val.encode('utf-8')).decode('utf-8')
    except: return "[Erreur Dechiffrement]"

def calculate_hmac(file_path):
    env_key = os.getenv("FERNET_SECRET_KEY")
    if not env_key:
        try:
            out = subprocess.check_output(
                ["docker", "exec", "monitor_dashboard", "cat", "/infrastructure/Docker/TP-Docker-Projet-Annuel/.env"], 
                stderr=subprocess.DEVNULL
            ).decode('utf-8')
            for line in out.splitlines():
                if line.strip().startswith('FERNET_SECRET_KEY='):
                    env_key = line.split('=', 1)[1].strip()
                    break
        except Exception:
            pass
            
    if not env_key: return None
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        return hmac.new(env_key.encode('utf-8'), data, hashlib.sha256).hexdigest()
    except: return None

def atomic_update_database(json_path, data, cipher):
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=4)
    
    new_hmac = calculate_hmac(json_path)
    if new_hmac:
        with open(HMAC_SIGN_FILE, 'w') as f:
            f.write(new_hmac)
            
    try:
        if cipher:
            encrypted_shadow = cipher.encrypt(json.dumps(data).encode('utf-8'))
            with open(SHADOW_BACKUP, 'wb') as f:
                f.write(encrypted_shadow)
    except Exception as e:
        logging.error(f"[SHADOW BACKUP] Erreur d'ecriture : {e}")

def restore_from_backup(json_path, cipher):
    if os.path.exists(SHADOW_BACKUP):
        try:
            with open(SHADOW_BACKUP, "rb") as f:
                decrypted = cipher.decrypt(f.read())
            with open(json_path, "wb") as f:
                f.write(decrypted)
            new_hmac = calculate_hmac(json_path)
            if new_hmac:
                with open(HMAC_SIGN_FILE, 'w') as f:
                    f.write(new_hmac)
            return True
        except:
            pass

    all_backups = glob.glob(os.path.join(BACKUP_DATA_DIR, "*.zip.enc"))
    if not all_backups:
        return False
        
    latest_backup = max(all_backups, key=os.path.getctime)
    try:
        with open(latest_backup, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = cipher.decrypt(encrypted_data)
        restored = False
        with zipfile.ZipFile(io.BytesIO(decrypted_data)) as z:
            for member in z.namelist():
                if "users_docker.json" in member:
                    with open(json_path, "wb") as target_f:
                        target_f.write(z.read(member))
                    restored = True
                    break
        if restored:
            new_hmac = calculate_hmac(json_path)
            if new_hmac:
                with open(HMAC_SIGN_FILE, 'w') as f:
                    f.write(new_hmac)
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                encrypted_shadow = cipher.encrypt(json.dumps(data).encode('utf-8'))
                with open(SHADOW_BACKUP, 'wb') as f:
                    f.write(encrypted_shadow)
            except:
                pass
            return True
    except:
        pass
    return False

def verify_and_restore_integrity(json_path, cipher):
    trigger_restore = False
    reason = ""
    
    if not os.path.exists(json_path):
        if not os.path.exists(SHADOW_BACKUP) and not glob.glob(os.path.join(BACKUP_DATA_DIR, "*.zip.enc")):
            return 
        trigger_restore = True
        reason = "Fichier JSON principal introuvable (Suppression suspecte)."
    else:
        current_hmac = calculate_hmac(json_path)
        if os.path.exists(HMAC_SIGN_FILE):
            with open(HMAC_SIGN_FILE, 'r') as f:
                stored_hmac = f.read().strip()
            if current_hmac != stored_hmac:
                trigger_restore = True
                reason = "Fichier JSON modifie manuellement (Signature invalide)."
        else:
            if not os.path.exists(SHADOW_BACKUP) and not glob.glob(os.path.join(BACKUP_DATA_DIR, "*.zip.enc")):
                if current_hmac:
                    with open(HMAC_SIGN_FILE, 'w') as f: f.write(current_hmac)
                return
            trigger_restore = True
            reason = "Fichier de signature HMAC introuvable."
    
    if trigger_restore:
        print(f"\n{C_DANGER}[!!!] ALERTE VIOLATION D'INTEGRITE [!!!]{C_END}")
        print(f"{C_WARN}{reason}{C_END}")
        print(f"{C_BASE}[*] Tentative de restauration automatique...{C_END}")
        logging.critical(f"[INTEGRITE] {reason} Restauration declenchee.")
        
        if restore_from_backup(json_path, cipher):
            print(f"{C_OK}[+] Base de donnees restauree avec succes.{C_END}\n")
            time.sleep(2)
        else:
            print(f"{C_DANGER}[!] Erreur fatale : Impossible de restaurer la base. Systeme verrouille.{C_END}")
            time.sleep(4)
            sys.exit(1)

class DBLock:
    def __init__(self, path, timeout=5):
        self.lockfile = path + ".lock"
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                self.fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return self
            except FileExistsError:
                time.sleep(0.1)
        raise Exception("Timeout : La base de donnees est actuellement utilisee.")

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.fd: os.close(self.fd)
            os.remove(self.lockfile)
        except Exception: pass

def safe_update_user(json_path, username, updates, cipher):
    with DBLock(json_path):
        verify_and_restore_integrity(json_path, cipher)
        with open(json_path, 'r') as f:
            data = json.load(f)
        if username in data:
            for k, v in updates.items():
                data[username][k] = v
            atomic_update_database(json_path, data, cipher)

def check_password_complexity(pwd_str):
    missing = []
    if len(pwd_str) < 12: missing.append("12 caracteres minimum")
    if not any(c.isupper() for c in pwd_str): missing.append("une majuscule")
    if not any(c.islower() for c in pwd_str): missing.append("une minuscule")
    if not any(c.isdigit() for c in pwd_str): missing.append("un chiffre")
    if not any(c in string.punctuation for c in pwd_str): missing.append("un symbole specifique (!@#$%^&*...)")
    return missing

def start_internal_login():
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    json_path = "/app/Data/Users/users_docker.json"
    cipher = get_cipher()
    
    console_failed_attempts = 0

    while True:
        console_lock_until = get_console_lock()
        current_time = time.time()
        
        if current_time < console_lock_until:
            while current_time < console_lock_until:
                remaining = int(console_lock_until - current_time)
                os.system('clear')
                print(f"{C_DANGER}==================================================={C_END}")
                print(f"{C_DANGER}       ALERTE : CONSOLE VERROUILLEE                {C_END}")
                print(f"{C_DANGER}==================================================={C_END}\n")
                print(f"{C_WARN}Le nombre maximum de tentatives a ete atteint.{C_END}")
                print(f"Veuillez patienter {remaining} secondes...\n")
                time.sleep(1)
                current_time = time.time()
            if os.path.exists(CONSOLE_LOCK_FILE):
                os.remove(CONSOLE_LOCK_FILE)
        
        os.system('clear')
        print(f"{C_WARN}**********************************************")
        print(f"* CYBER MONITOR : SECURE ACCESS CONTROL      *")
        print(f"**********************************************{C_END}\n")

        user = input("Identifiant : ").strip().lower()
        if not user:
            continue
            
        pwd_input = getpass.getpass("Mot de passe : ").strip()
        print()
        
        try:
            with DBLock(json_path):
                verify_and_restore_integrity(json_path, cipher)
                with open(json_path, 'r') as f:
                    accounts = json.load(f)
        except Exception as e:
            print(f"{C_DANGER}[!] ERREUR 100 : Erreur de lecture de la base.{C_END}")
            time.sleep(3)
            sys.exit(1)

        user_exists = user in accounts
        stored_hash = accounts.get(user, {}).get("password", "").encode('utf-8') if user_exists else bcrypt.hashpw(b"dummy", bcrypt.gensalt())
        
        try:
            password_match = bcrypt.checkpw(pwd_input.encode('utf-8'), stored_hash)
        except ValueError:
            password_match = False

        is_success = user_exists and password_match

        if not is_success:
            console_failed_attempts += 1
            if user_exists:
                failed_attempts = accounts[user].get("failed_attempts", 0) + 1
                safe_update_user(json_path, user, {"failed_attempts": failed_attempts}, cipher)
                log_security_event(user, "LOGIN_FAILED", "WARNING", f"Mot de passe incorrect (Tentative n {failed_attempts})")
            else:
                log_security_event(user, "UNKNOWN_USER", "WARNING", "Tentative de connexion avec un identifiant inexistant")
            
            print(f"{C_DANGER}[!] ERREUR 200 : Identifiants incorrects.{C_END}")
            
            if console_failed_attempts % 3 == 0:
                console_lock_until = time.time() + 60
                set_console_lock(console_lock_until)
                log_security_event("CONSOLE", "CONSOLE_LOCKED", "CRITICAL", "La console a ete verrouillee pour 60s apres 3 echecs")
            else:
                time.sleep(2)
            continue

        console_failed_attempts = 0
        user_data = accounts[user]

        if user_data.get("blocked", False):
            log_security_event(user, "ACCESS_DENIED", "CRITICAL", "Tentative de connexion sur un compte bloque par l'administrateur")
            print(f"{C_DANGER}[!] ERREUR 403 : ACCES REFUSE.{C_END}")
            print(f"{C_WARN}Ce compte a ete suspendu par un administrateur.{C_END}")
            time.sleep(3)
            sys.exit(1)

        role = user_data.get("role", "user")
        assigned = user_data.get("assigned_assets", [])
        
        if role == "user" and MACHINE_NAME not in assigned:
            log_security_event(user, "ACCESS_DENIED", "CRITICAL", f"Tentative d'acces hors perimetre sur {MACHINE_NAME}")
            print(f"\n{C_DANGER}[!] ACCES REFUSE : Vous n'avez pas l'autorisation d'acceder a l'equipement {MACHINE_NAME}.{C_END}")
            time.sleep(3)
            sys.exit(1)

        failed_count = user_data.get("failed_attempts", 0)

        if failed_count > SEUIL_CRITIQUE:
            print(f"\n{C_DANGER}[!] ALERTE MAXIMALE : {failed_count} TENTATIVES ECHOUEES DETECTEES [!]{C_END}")
            print(f"{C_WARN}Par mesure de precaution, vous devez obligatoirement changer votre mot de passe.{C_END}\n")
            log_security_event(user, "CRITICAL_SECURITY_TRIGGER", "CRITICAL", f"Reinitialisation forcee apres {failed_count} echecs")
            time.sleep(3)
            safe_update_user(json_path, user, {"force_reset": True}, cipher)
            user_data["force_reset"] = True

        elif SEUIL_AVERTISSEMENT <= failed_count <= SEUIL_CRITIQUE:
            print(f"\n{C_DANGER}==================================================={C_END}")
            print(f"{C_DANGER}[!] AVERTISSEMENT DE SECURITE [!]{C_END}")
            print(f"{C_WARN}Le systeme a detecte {failed_count} tentative(s) de connexion echouee(s){C_END}")
            print(f"{C_WARN}sur votre identifiant depuis votre derniere session.{C_END}")
            print(f"{C_DANGER}==================================================={C_END}\n")
            log_security_event(user, "SECURITY_WARNING_SEEN", "INFO", f"Notification de {failed_count} echecs precedents")
            
            resp = input(f"{C_BASE}Etes-vous a l'origine de ces tentatives echouees ? (o/n) : {C_END}").strip().lower()
            
            if resp != 'o':
                print(f"\n{C_WARN}[!] PROCEDURE DE SECURITE ENCLENCHEE : VERIFICATION D'IDENTITE{C_END}")
                
                fields_map = {
                    "nom": "Nom de famille", "prenom": "Prenom", "email": "Adresse Email",
                    "phone": "Numero de telephone", "entreprise": "Entreprise", 
                    "secteur": "Secteur d'activite", "poste": "Poste occupe"
                }
                
                available_fields = []
                for k, display in fields_map.items():
                    if k in user_data:
                        dec = decrypt_val(user_data[k], cipher)
                        if dec and dec not in ["Non renseigne", "[Erreur Dechiffrement]"]:
                            available_fields.append((display, dec))
                            
                if available_fields:
                    question, expected_answer = random.choice(available_fields)
                    identity_confirmed = False
                    
                    for attempt_id in range(10, 0, -1):
                        ans = input(f"[{attempt_id} essai(s)] Saisissez votre {question} : ").strip()
                        if ans.lower() == expected_answer.lower():
                            identity_confirmed = True
                            break
                        else:
                            print(f"{C_DANGER}Reponse incorrecte.{C_END}")
                    
                    if identity_confirmed:
                        print(f"{C_OK}[+] Identite confirmee.{C_END}")
                        print(f"{C_WARN}Par precaution, vous devez modifier votre mot de passe immediatement.{C_END}")
                        safe_update_user(json_path, user, {"force_reset": True}, cipher)
                        user_data["force_reset"] = True
                    else:
                        print(f"{C_DANGER}[!] ERREUR : IDENTITE NON CONFIRMEE.{C_END}")
                        print(f"{C_WARN}La session va etre interrompue pour des raisons de securite.{C_END}") 
                        log_security_event(user, "IDENTITY_VERIFICATION_FAILED", "WARNING", f"Echec de verification d'identite")
                        time.sleep(3)
                        sys.exit(1)
                else:
                    print(f"{C_WARN}[!] Aucune information de profil disponible pour la verification.{C_END}")
                    print(f"{C_WARN}Par mesure de precaution absolue, vous devez modifier votre mot de passe.{C_END}")
                    safe_update_user(json_path, user, {"force_reset": True}, cipher)
                    user_data["force_reset"] = True

        if failed_count > 0:
            safe_update_user(json_path, user, {"failed_attempts": 0, "lock_until": 0}, cipher)
            user_data["failed_attempts"] = 0

        if user_data.get("force_reset"):
            print(f"\n{C_WARN}[!] MISE A JOUR DE SECURITE REQUISE.{C_END}")
            print(f"Vous devez obligatoirement modifier votre mot de passe pour continuer.\n")
            while True:
                new_pwd = getpass.getpass("\nNouveau mot de passe : ").strip()
                if not new_pwd:
                    continue
                missing = check_password_complexity(new_pwd)
                if missing:
                    print(f"{C_DANGER}Mot de passe invalide. Il manque : {', '.join(missing)}{C_END}\n")
                    time.sleep(2)
                    continue
                confirm = getpass.getpass("Confirmez le mot de passe : ").strip()
                if new_pwd != confirm:
                    print(f"{C_DANGER}Les mots de passe ne correspondent pas. Reessayez.{C_END}\n")
                    time.sleep(2)
                    continue
                
                try:
                    if bcrypt.checkpw(new_pwd.encode('utf-8'), stored_hash):
                        print(f"{C_DANGER}Le nouveau mot de passe doit etre different de l'ancien.{C_END}\n")
                        time.sleep(2)
                        continue
                except ValueError: pass 

                new_hashed = bcrypt.hashpw(new_pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                break

            try:
                safe_update_user(json_path, user, {
                    "password": new_hashed,
                    "force_reset": False,
                    "reset_by_admin": False
                }, cipher)
                
                log_security_event(user, "PASSWORD_RESET", "INFO", "L'utilisateur a reinitialise son mot de passe avec succes")
                print(f"{C_OK}[+] Mot de passe mis a jour avec succes.{C_END}")
                time.sleep(2)
            except Exception as e:
                print(f"{C_DANGER}Erreur BDD lors de la sauvegarde : {e}{C_END}")
                time.sleep(3)
                sys.exit(1)
                
        user_email = decrypt_val(user_data.get("email"), cipher)
        if user_email and user_email != "Non renseigne":
            expected_code = str(secrets.randbelow(900000) + 100000)
            msg = MIMEText(f"Bonjour,\n\nVotre code MFA a usage unique pour l'acces SSH a la machine {MACHINE_NAME} est : {expected_code}\n\nL'equipe SOC.")
            msg['Subject'] = f'CyberMonitors - Code MFA pour {MACHINE_NAME}'
            msg['From'] = os.getenv("EMAIL_USER")
            msg['To'] = user_email
            
            try:
                host = os.getenv("EMAIL_HOST")
                port = int(os.getenv("EMAIL_PORT", 587))
                pwd_app = os.getenv("EMAIL_PASSWORD")
                mail_user = os.getenv("EMAIL_USER")

                print(f"\n{C_BASE}[*] VERIFICATION MFA : Envoi du code a {user_email}...{C_END}")
                log_security_event(user, "MFA_CHALLENGE_SENT", "INFO", "Envoi du code MFA par email post-authentification")

                if port == 465:
                    with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                        server.login(mail_user, pwd_app)
                        server.sendmail(mail_user, [user_email], msg.as_string())
                else:
                    with smtplib.SMTP(host, port, timeout=10) as server:
                        server.starttls()
                        server.login(mail_user, pwd_app)
                        server.sendmail(mail_user, [user_email], msg.as_string())
            except Exception as e:
                print(f"{C_DANGER}[!] Erreur d'envoi du code MFA SMTP : {e}{C_END}")
                sys.exit(1)

            attempts = 3
            mfa_success = False
            while attempts > 0:
                code_in = input(f"{C_WARN}Code MFA recu par email : {C_END}").strip()
                if code_in == expected_code:
                    mfa_success = True
                    break
                attempts -= 1
                if attempts > 0:
                    print(f"{C_DANGER}Code invalide. Essais restants : {attempts}{C_END}")
            
            if not mfa_success:
                log_security_event(user, "MFA_FAILED", "CRITICAL", "Echec lors de la validation du code MFA par mail")
                print(f"{C_DANGER}Echec MFA. Connexion coupee.{C_END}")
                sys.exit(1)
            else:
                log_security_event(user, "MFA_SUCCESS", "INFO", "Validation MFA reussie")
        else:
            print(f"{C_DANGER}[!] Adresse email non configuree. MFA impossible. Acces bloque.{C_END}")
            sys.exit(1)

        break 

    log_security_event(user, "LOGIN_SUCCESS", "INFO", "Ouverture de session SSH accordee")
    print(f"{C_OK}[+] Authentification double facteur reussie.{C_END}")
    time.sleep(1)
    
    os_type = os.environ.get('OS_TYPE', 'Linux')
    shell_path = "/bin/bash.real" 
    
    if os_type == "Windows":
        pwsh_loc = shutil.which("pwsh")
        if pwsh_loc and os.path.exists(pwsh_loc): shell_path = pwsh_loc
        elif os.path.exists("/opt/microsoft/powershell/7/pwsh"): shell_path = "/opt/microsoft/powershell/7/pwsh"
        elif os.path.exists("/usr/bin/pwsh"): shell_path = "/usr/bin/pwsh"
        else:
            print(f"{C_WARN}[!] PowerShell introuvable. Chargement d'un terminal de secours...{C_END}")
            time.sleep(2)
    
    try:
        user_info = pwd.getpwnam(user)
        print(f"{C_BASE}[*] Espace local detecte. Chargement du profil '{user}'...{C_END}")
        time.sleep(1)
    except KeyError:
        print(f"{C_WARN}[*] Profil local inexistant. Creation de l'espace dedie en cours...{C_END}")
        time.sleep(2)
        try:
            subprocess.run(["useradd", "-m", "-s", shell_path, user], check=True, capture_output=True, text=True)
            print(f"{C_OK}[+] Espace '{user}' cree avec succes sur le disque.{C_END}")
            time.sleep(1)
            user_info = pwd.getpwnam(user)
        except subprocess.CalledProcessError as e:
            print(f"{C_DANGER}[!] ERREUR 301 : Echec de la commande 'useradd'.{C_END}")
            print(f"Details : {e.stderr.strip()}")
            time.sleep(3)
            sys.exit(1)
        except Exception as e:
            print(f"{C_DANGER}[!] ERREUR 302 : Panne systeme inattendue lors de la creation.{C_END}")
            print(f"Details : {e}")
            time.sleep(3)
            sys.exit(1)

    print(f"{C_BASE}[*] Initialisation de la session...{C_END}")
    time.sleep(1)

    env = os.environ.copy()
    env['INTERNAL_LOGGED_IN'] = "1" 
    env['TMOUT'] = "300" 

    if role == "admin":
        print(f"{C_WARN}[!] Elevation des privileges : Acces Administrateur (ROOT) accorde.{C_END}")
        time.sleep(2)
        env['HOME'] = '/root'
        env['USER'] = 'root'
        os.setgid(0)
        os.setuid(0)
        os.chdir('/root')
    else:
        env['HOME'] = user_info.pw_dir
        env['USER'] = user
        os.setgid(user_info.pw_gid)
        os.setuid(user_info.pw_uid)
        os.chdir(user_info.pw_dir)

    try: os.execlpe(shell_path, shell_path, env)
    except Exception as e:
        print(f"{C_DANGER}[!] ERREUR 401 : Impossible de lancer le terminal virtuel.{C_END}")
        print(f"Details : {e}")
        time.sleep(3)
        sys.exit(1)

if __name__ == "__main__":
    start_internal_login()