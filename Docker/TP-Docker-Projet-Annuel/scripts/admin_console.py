import builtins
import getpass
import sys
import time
import os
import subprocess
import threading
import queue
import bcrypt
import shutil
import re
import json
import logging
import secrets
import string
import uuid
import glob
import tempfile
import zipfile
import io
import zlib  
import stat  
import hmac
import hashlib
import random
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# *** PROTECTION GLOBALE : CRASH CTRL+D ET TIMEOUT D'INACTIVITE ***
def input_with_timeout(prompt="", timeout=300, is_password=False):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    start_time = time.time()
    input_str = ""
    
    if os.name == 'nt':
        import msvcrt
        while True:
            if msvcrt.kbhit():
                start_time = time.time() # Reinitialise le chrono a chaque frappe
                c = msvcrt.getch()
                if c == b'\r' or c == b'\n':
                    print()
                    return input_str
                elif c == b'\x08': # Backspace
                    if len(input_str) > 0:
                        input_str = input_str[:-1]
                        if not is_password:
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()
                elif c == b'\x03' or c == b'\x04': # Ctrl+C / Ctrl+D
                    print()
                    return ""
                else:
                    try:
                        char = c.decode('utf-8')
                        input_str += char
                        if not is_password:
                            sys.stdout.write(char)
                            sys.stdout.flush()
                    except:
                        pass
            if time.time() - start_time > timeout:
                print("\n\n\033[91m[!] ALERTE DE SECURITE : Session expiree suite a 5 minutes d'inactivite.\033[0m")
                sys.exit(0)
            time.sleep(0.05)
    else:
        import select
        import termios
        
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        if is_password:
            new_settings = termios.tcgetattr(fd)
            new_settings[3] = new_settings[3] & ~termios.ECHO
            termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)
            
        try:
            while True:
                ready, _, _ = select.select([sys.stdin], [], [], 0.05)
                if ready:
                    line = sys.stdin.readline()
                    if is_password:
                        print()
                    if not line:
                        return ""
                    return line.rstrip('\n')
                if time.time() - start_time > timeout:
                    if is_password:
                        print()
                    print("\n\n\033[91m[!] ALERTE DE SECURITE : Session expiree suite a 5 minutes d'inactivite.\033[0m")
                    sys.exit(0)
        finally:
            if is_password:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def safe_input(prompt=""):
    return input_with_timeout(prompt, timeout=300, is_password=False)

def safe_getpass(prompt=""):
    return input_with_timeout(prompt, timeout=300, is_password=True)

builtins.input = safe_input
getpass.getpass = safe_getpass

# *** PARAMETRES DE SECURITE ***
SEUIL_CRITIQUE = 10       
SEUIL_AVERTISSEMENT = 3   

# *** DETECTION DOCKER ***
IN_DOCKER = os.getenv("IS_MASTER_CONSOLE") == "1"

current_dir = os.path.dirname(os.path.abspath(__file__))

if IN_DOCKER:
    ROOT_BACKUP_DIR  = "/infrastructure"
    log_dir          = "/infrastructure/Data/Logs"
    BACKUP_PREFS_DIR = "/infrastructure/code_monitoring/gestion de sauvegarde"
    BACKUP_DATA_DIR  = "/infrastructure/Data/backups"
    USER_DATA_PATH   = "/infrastructure/Data/Users/users_docker.json"
    HMAC_SIGN_FILE   = "/infrastructure/Data/Users/.users_docker.hmac"
    SHADOW_BACKUP    = "/infrastructure/Data/Users/.users_docker.shadow.enc"
    env_path         = "/infrastructure/Docker/TP-Docker-Projet-Annuel/.env"
else:
    ROOT_BACKUP_DIR  = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
    log_dir          = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "Data", "Logs"))
    BACKUP_PREFS_DIR = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "code_monitoring", "gestion de sauvegarde"))
    BACKUP_DATA_DIR  = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "Data", "backups"))
    USER_DATA_PATH   = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "Data", "Users", "users_docker.json"))
    HMAC_SIGN_FILE   = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "Data", "Users", ".users_docker.hmac"))
    SHADOW_BACKUP    = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "Data", "Users", ".users_docker.shadow.enc"))
    env_path         = os.path.abspath(os.path.join(current_dir, "..", ".env"))

os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "Logs_Console_Admin.log")

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# *** DESIGN ***
C_BASE = '\033[96m'
C_OK = '\033[92m'
C_WARN = '\033[93m'
C_DANGER = '\033[91m'
C_END = '\033[0m'

def display_lockout_screen(lock_until):
    while True:
        remaining = int(lock_until - time.time())
        if remaining <= 0:
            break
        
        m, s = divmod(remaining, 60)
        h, m = divmod(m, 60)
        
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{C_DANGER}==================================================={C_END}")
        print(f"{C_DANGER}       ALERTE DE SECURITE : ACCES VERROUILLE       {C_END}")
        print(f"{C_DANGER}==================================================={C_END}\n")
        print(f"{C_WARN}Suite a de multiples tentatives de connexion echouees,{C_END}")
        print(f"{C_WARN}ce terminal a ete temporairement suspendu pour des{C_END}")
        print(f"{C_WARN}raisons de securite.{C_END}\n")
        print(f"{C_DANGER}[!] CET INCIDENT A ETE REPORTE AUX ADMINISTRATEURS [!]{C_END}\n")
        print(f"Temps restant avant deblocage automatique : {C_WARN}{h:02d}h {m:02d}m {s:02d}s{C_END}")
        
        time.sleep(1)
    
    os.system('cls' if os.name == 'nt' else 'clear')

# *** CHIFFREMENT (FERNET) VIA .ENV ***
load_dotenv(dotenv_path=env_path)
env_key = os.getenv("FERNET_SECRET_KEY")

if not env_key:
    print(f"{C_DANGER}Erreur fatale : Clef FERNET_SECRET_KEY introuvable dans le fichier .env !{C_END}")
    sys.exit(1)

try:
    SECRET_KEY = env_key.encode('utf-8')
    cipher = Fernet(SECRET_KEY)
except Exception as e:
    print(f"{C_DANGER}Erreur fatale de chiffrement (Clef invalide) : {e}{C_END}")
    sys.exit(1)

def encrypt_val(val):
    if not val or val == "Non renseigne": 
        return "Non renseigne"
    return cipher.encrypt(val.encode('utf-8')).decode('utf-8')

def decrypt_val(val):
    if not val or val == "Non renseigne": 
        return "Non renseigne"
    try:
        return cipher.decrypt(val.encode('utf-8')).decode('utf-8')
    except:
        return "[Erreur Dechiffrement]"

def calculate_hmac(file_path):
    if not env_key: return None
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        return hmac.new(env_key.encode('utf-8'), data, hashlib.sha256).hexdigest()
    except: return None

# *** ARCHITECTURE SHADOW BACKUP ***
def atomic_update_database(json_path, data):
    """Met a jour le JSON, le HMAC et le Shadow Backup en une seule operation."""
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=4)
    
    new_hmac = calculate_hmac(json_path)
    if new_hmac:
        with open(HMAC_SIGN_FILE, 'w') as f:
            f.write(new_hmac)
            
    try:
        encrypted_shadow = cipher.encrypt(json.dumps(data).encode('utf-8'))
        with open(SHADOW_BACKUP, 'wb') as f:
            f.write(encrypted_shadow)
    except Exception as e:
        logging.error(f"[SHADOW BACKUP] Erreur d'ecriture : {e}")

def restore_from_backup(json_path):
    """Restaure depuis le Shadow Backup en priorite, sinon depuis le ZIP."""
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
            
            # Reconstruction automatique du Shadow Backup apres restauration ZIP
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

def verify_and_restore_integrity(json_path):
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
        
        if restore_from_backup(json_path):
            print(f"{C_OK}[+] Base de donnees restauree avec succes.{C_END}\n")
            time.sleep(2)
        else:
            print(f"{C_DANGER}[!] Erreur fatale : Impossible de restaurer la base. Systeme verrouille.{C_END}")
            time.sleep(4)
            sys.exit(1)

# *** CONFIGURATION DES BACKUPS ***
os.makedirs(BACKUP_PREFS_DIR, exist_ok=True)
BACKUP_CONFIG_FILE = os.path.join(BACKUP_PREFS_DIR, "backup_config.json")
os.makedirs(BACKUP_DATA_DIR, exist_ok=True)

COUNTRIES = {
    'fr': {'code': '+33', 'len': 9, 'name': 'France'},
    'be': {'code': '+32', 'len': 9, 'name': 'Belgique'},
    'ch': {'code': '+41', 'len': 9, 'name': 'Suisse'},
    'ca': {'code': '+1', 'len': 10, 'name': 'Canada'},
    'us': {'code': '+1', 'len': 10, 'name': 'Etats-Unis'},
    'lu': {'code': '+352', 'len': 9, 'name': 'Luxembourg'},
    'uk': {'code': '+44', 'len': 10, 'name': 'Royaume-Uni'}
}

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
        raise Exception("Timeout : La base de donnees est actuellement utilisee par un autre processus.")

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.fd: 
                os.close(self.fd)
            os.remove(self.lockfile)
        except Exception: 
            pass

def safe_update_user(json_path, username, updates):
    with DBLock(json_path):
        verify_and_restore_integrity(json_path)
        with open(json_path, 'r') as f:
            data = json.load(f)
        if username in data:
            for k, v in updates.items():
                data[username][k] = v
            atomic_update_database(json_path, data)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def run(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.returncode
    except: 
        return "", 1

def is_docker_alive():
    _, code = run("docker info")
    return code == 0

def is_container_running(name):
    stat, _ = run(f'docker inspect -f "{{{{.State.Running}}}}" {name}')
    return stat == "true"

def get_machines():
    out, code = run('docker ps -a --format "{{.Names}}|{{.Status}}"')
    machines = []
    if out and code == 0:
        for line in out.split('\n'):
            if '|' in line:
                name, status = line.split('|', 1)
                if any(x in name.lower() for x in ['srv', 'wkst', 'center']):
                    machines.append({"name": name, "status": status})
    return machines

def check_password_complexity(pwd):
    missing = []
    if len(pwd) < 6: missing.append("6 caracteres minimum")
    if not any(c.isupper() for c in pwd): missing.append("une majuscule")
    if not any(c.islower() for c in pwd): missing.append("une minuscule")
    if not any(c.isdigit() for c in pwd): missing.append("un chiffre")
    if not any(c in string.punctuation for c in pwd): missing.append("un symbole specifique (!@#$%^&*...)")
    return missing

def is_unique(users, field, value):
    if not value or value == "Non renseigne": 
        return True
    for u, data in users.items():
        if field in data and decrypt_val(data[field]) == value:
            return False
    return True

def manage_own_profile(current_user):
    clear_screen()
    print(f"{C_BASE}*** MON PROFIL ({current_user}) ***{C_END}\n")
    
    print(f"{C_WARN}Pour des raisons de securite, veuillez confirmer votre mot de passe.{C_END}")
    pwd = getpass.getpass("Mot de passe : ").strip()
    
    try:
        with DBLock(USER_DATA_PATH):
            verify_and_restore_integrity(USER_DATA_PATH)
            with open(USER_DATA_PATH, 'r') as f:
                users = json.load(f)
    except Exception as e:
        print(f"{C_DANGER}Erreur de lecture du fichier : {e}{C_END}")
        time.sleep(2)
        return

    stored_hash = users[current_user].get("password", "").encode('utf-8')
    try:
        match = bcrypt.checkpw(pwd.encode('utf-8'), stored_hash)
    except:
        match = False
        
    if not match:
        print(f"{C_DANGER}[!] Mot de passe incorrect.{C_END}")
        time.sleep(2)
        return

    while True:
        try:
            with DBLock(USER_DATA_PATH):
                verify_and_restore_integrity(USER_DATA_PATH)
                with open(USER_DATA_PATH, 'r') as f:
                    users = json.load(f)
        except Exception as e:
            print(f"{C_DANGER}Erreur de lecture : {e}{C_END}")
            time.sleep(2)
            break
            
        u_data = users[current_user]
        clear_screen()
        print(f"{C_BASE}=== VOS INFORMATIONS ==={C_END}\n")
        print(f"Nom        : {decrypt_val(u_data.get('nom', ''))}")
        print(f"Prenom     : {decrypt_val(u_data.get('prenom', ''))}")
        print(f"Email      : {decrypt_val(u_data.get('email', ''))}")
        print(f"Telephone  : {decrypt_val(u_data.get('phone', ''))}")
        print(f"Entreprise : {decrypt_val(u_data.get('entreprise', ''))}")
        print(f"Secteur    : {decrypt_val(u_data.get('secteur', ''))}")
        print(f"Poste      : {decrypt_val(u_data.get('poste', ''))}")
        
        print(f"\n{C_OK}*** QUE VOULEZ-VOUS MODIFIER ? ***{C_END}")
        print("1. Mon Email")
        print("2. Mon Telephone")
        print("3. Mes Informations Pro (Entreprise, Secteur, Poste)")
        print("4. Mon Mot de passe")
        print("0. Retour au menu principal")
        
        choice = input("\nChoix : ").strip()
        if choice == '0' or choice == '':
            break
            
        field_updates = {}
        
        if choice == '1':
            em = input("Nouvel Email (vide pour vider) : ").strip()
            if em and not re.match(r"^[^@]+@[^@]+\.[^@]+$", em):
                print(f"{C_DANGER}Format invalide.{C_END}")
                time.sleep(2)
                continue
            if em and not is_unique(users, "email", em):
                print(f"{C_DANGER}Email deja utilise.{C_END}")
                time.sleep(2)
                continue
            field_updates["email"] = encrypt_val(em if em else "Non renseigne")
            
        elif choice == '2':
            c_code = input("Code pays (ex: FR, 'liste' pour voir, vide pour vider) : ").strip().lower()
            if not c_code: 
                field_updates["phone"] = encrypt_val("Non renseigne")
            else:
                if c_code == 'liste':
                    for k, v in COUNTRIES.items(): 
                        print(f"   - {k.upper()} : {v['name']} ({v['code']})")
                    input("Appuyez sur Entree...")
                    continue
                if c_code not in COUNTRIES:
                    print(f"{C_DANGER}Pays inconnu.{C_END}")
                    time.sleep(2)
                    continue
                country = COUNTRIES[c_code]
                num = input(f"Numero {country['code']} : ").strip()
                num = num.replace(" ", "").replace(".", "").replace("-", "")
                if num.startswith(country['code']): 
                    num = num[len(country['code']):]
                if num.startswith('0'): 
                    num = num[1:]
                if len(num) != country['len']:
                    print(f"{C_DANGER}Taille invalide pour {c_code.upper()}.{C_END}")
                    time.sleep(2)
                    continue
                full = country['code'] + num
                if not is_unique(users, "phone", full):
                    print(f"{C_DANGER}Numero deja utilise.{C_END}")
                    time.sleep(2)
                    continue
                field_updates["phone"] = encrypt_val(full)
                
        elif choice == '3':
            ent = input("Entreprise (vide=conserver, 'vider'=effacer) : ").strip()
            sec = input("Secteur (vide=conserver, 'vider'=effacer) : ").strip()
            pos = input("Poste (vide=conserver, 'vider'=effacer) : ").strip()
            if ent: 
                field_updates["entreprise"] = encrypt_val("Non renseigne" if ent.lower() == 'vider' else ent)
            if sec: 
                field_updates["secteur"] = encrypt_val("Non renseigne" if sec.lower() == 'vider' else sec)
            if pos: 
                field_updates["poste"] = encrypt_val("Non renseigne" if pos.lower() == 'vider' else pos)
                
        elif choice == '4':
            print("\nChangement de mot de passe :")
            cancel_pwd = False
            while True:
                new_pwd = getpass.getpass("Nouveau mot de passe ('0' pour annuler) : ").strip()
                if new_pwd == '0' or new_pwd == '': 
                    cancel_pwd = True
                    break
                missing = check_password_complexity(new_pwd)
                if missing: 
                    print(f"{C_DANGER}Invalide. Manque : {', '.join(missing)}{C_END}")
                    continue
                
                try:
                    if bcrypt.checkpw(new_pwd.encode('utf-8'), stored_hash):
                        print(f"{C_DANGER}Le nouveau mot de passe doit etre different de l'ancien.{C_END}")
                        continue
                except: pass
                
                confirm = getpass.getpass("Confirmez : ").strip()
                if new_pwd != confirm: 
                    print(f"{C_DANGER}Correspondance echouee.{C_END}")
                    continue
                break
                
            if cancel_pwd: 
                continue
            
            field_updates["password"] = bcrypt.hashpw(new_pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            logging.info(f"[{current_user}] a change son propre mot de passe.")

        if field_updates:
            try:
                safe_update_user(USER_DATA_PATH, current_user, field_updates)
                print(f"{C_OK}[+] Vos informations ont ete mises a jour avec succes.{C_END}")
                logging.info(f"[{current_user}] a mis a jour son profil.")
                time.sleep(2)
            except Exception as e: 
                print(f"{C_DANGER}Erreur de sauvegarde : {e}{C_END}")
                time.sleep(3)

# *** PATCH DE LA BASE DE DONNEES ***
def patch_database():
    try:
        if not os.path.exists(USER_DATA_PATH): 
            return
        with DBLock(USER_DATA_PATH):
            verify_and_restore_integrity(USER_DATA_PATH)
            with open(USER_DATA_PATH, 'r') as f: 
                users = json.load(f)
            changed = False
            for u, data in users.items():
                if "id" not in data:
                    data["id"] = str(uuid.uuid4())
                    changed = True
                if "blocked" not in data:
                    data["blocked"] = False
                    changed = True
                if "force_reset" not in data:
                    data["force_reset"] = False
                    changed = True
                if "reset_by_admin" not in data:
                    data["reset_by_admin"] = False
                    changed = True
            
            if changed:
                atomic_update_database(USER_DATA_PATH, users)
                logging.info("Mise a jour de la base de donnees effectuee (Signature HMAC incluse).")
    except Exception as e:
        logging.error(f"Erreur lors du patch de la BDD : {e}")

# *** FONCTIONS BACKUP ***
def load_backup_config():
    default_config = {
        "interval_type": "days", 
        "interval_value": 7,      
        "retention_count": 5      
    }
    if os.path.exists(BACKUP_CONFIG_FILE):
        with open(BACKUP_CONFIG_FILE, "r") as f:
            return json.load(f)
    else:
        with open(BACKUP_CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=4)
        return default_config

def save_backup_config(config):
    with open(BACKUP_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def run_full_backup(current_admin, silent=False):
    config = load_backup_config()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    temp_dir = tempfile.gettempdir()
    temp_zip_base = os.path.join(temp_dir, f"Backup_Full_{timestamp}")
    target_dir = ROOT_BACKUP_DIR
    
    if not silent:
        print(f"\n{C_BASE}[*] Lancement de la sauvegarde de l'infrastructure ({target_dir})...{C_END}")

    def zip_task():
        with zipfile.ZipFile(temp_zip_base + ".zip", 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(target_dir):
                if os.path.abspath(BACKUP_DATA_DIR) in os.path.abspath(root): 
                    continue
                for f in files:
                    try:
                        zf.write(os.path.join(root, f), os.path.relpath(os.path.join(root, f), target_dir))
                    except:
                        pass 

    thread = threading.Thread(target=zip_task)
    thread.start()

    steps = 50
    i = 0
    while thread.is_alive():
        percent = min((i / steps) * 99, 99)
        bar_len = int((percent / 100) * 20)
        bar = '=' * bar_len + ' ' * (20 - bar_len)
        if not silent:
            sys.stdout.write(f"\r[{bar}] {percent:.0f}%")
            sys.stdout.flush()
        time.sleep(0.2)
        i += 1

    thread.join()
    
    if not silent:
        sys.stdout.write(f"\r[{'=' * 20}] 100%\n")
        sys.stdout.flush()

    zip_file = temp_zip_base + ".zip"
    
    if not silent:
        print(f"{C_WARN}[*] Application du chiffrement AES (Fernet) sur l'archive...{C_END}")
        
    with open(zip_file, "rb") as f:
        zip_data = f.read()
    encrypted_data = cipher.encrypt(zip_data)
    
    final_encrypted_file = os.path.join(BACKUP_DATA_DIR, f"Backup_Full_{timestamp}.zip.enc")
    with open(final_encrypted_file, "wb") as f:
        f.write(encrypted_data)
        
    os.remove(zip_file)
    
    all_backups = glob.glob(os.path.join(BACKUP_DATA_DIR, "*.zip.enc"))
    all_backups.sort(key=os.path.getctime)
    
    while len(all_backups) > config["retention_count"]:
        oldest = all_backups.pop(0)
        os.remove(oldest)
        if not silent:
            print(f"{C_WARN}[-] Ancienne archive purgee : {os.path.basename(oldest)}{C_END}")
        logging.info(f"[BACKUP] Systeme a purge automatiquement l'archive {os.path.basename(oldest)}.")

    if not silent:
        print(f"{C_OK}[+] Sauvegarde finalisee et securisee avec succes !{C_END}")
        time.sleep(2)
        
    logging.info(f"[BACKUP] [{current_admin}] a realise une nouvelle sauvegarde avec succes.")

def check_auto_backup():
    config = load_backup_config()
    all_backups = glob.glob(os.path.join(BACKUP_DATA_DIR, "*.zip.enc"))
    
    needs_backup = False
    if not all_backups:
        needs_backup = True
    else:
        latest_backup = max(all_backups, key=os.path.getctime)
        last_time = datetime.fromtimestamp(os.path.getctime(latest_backup))
        
        if config["interval_type"] == "days":
            limit = last_time + timedelta(days=config["interval_value"])
        else:
            limit = last_time + timedelta(hours=config["interval_value"])
            
        if datetime.now() >= limit:
            needs_backup = True

    if needs_backup:
        print(f"\n{C_WARN}[!] Declenchement de la sauvegarde automatique requise.{C_END}")
        run_full_backup("SYSTEM_AUTO", silent=False)
        print(f"{C_OK}[+] Verification des backups terminee !{C_END}\n")
        time.sleep(1)

def decrypt_existing_backup(current_admin):
    all_backups = glob.glob(os.path.join(BACKUP_DATA_DIR, "*.zip.enc"))
    if not all_backups:
        print(f"{C_DANGER}[!] Aucune archive chiffree trouvee dans {BACKUP_DATA_DIR}.{C_END}")
        time.sleep(2)
        return

    print(f"\n{C_BASE}=== ARCHIVES DISPONIBLES ==={C_END}")
    for i, path in enumerate(all_backups):
        size = os.path.getsize(path) / (1024 * 1024)
        print(f"{i+1}. {os.path.basename(path)} ({size:.2f} Mo)")
    
    print("0. Annuler")
    
    try:
        c = input("\nQuelle archive dechiffrer ? (Numero) : ").strip()
        if c == '0' or c == '':
            return
            
        c = int(c)
        if 1 <= c <= len(all_backups):
            target_enc = all_backups[c-1]
            target_zip = target_enc.replace(".enc", "") 
            
            if os.path.exists(target_zip):
                print(f"\n{C_WARN}[!] Ce fichier a deja ete dechiffre et est present dans le dossier : {os.path.basename(target_zip)}{C_END}")
                input("Appuyez sur Entree pour revenir...")
                return

            print(f"{C_WARN}[*] Dechiffrement en cours...{C_END}")
            with open(target_enc, "rb") as f:
                encrypted_data = f.read()
            
            decrypted_data = cipher.decrypt(encrypted_data)
            
            with open(target_zip, "wb") as f:
                f.write(decrypted_data)
            
            print(f"{C_OK}[+] Succes ! L'archive est prete et lisible (WinRAR) : {os.path.basename(target_zip)}{C_END}")
            print(f"{C_WARN}N'oubliez pas de supprimer le .zip clair apres votre intervention via le menu de suppression.{C_END}")
            logging.warning(f"[BACKUP] [{current_admin}] a extrait la version dechiffree de {os.path.basename(target_enc)}")
            input("\nAppuyez sur Entree pour continuer...")
        else:
            print(f"{C_DANGER}Choix invalide.{C_END}")
            time.sleep(1)
    except ValueError:
        print(f"{C_DANGER}Entree invalide.{C_END}")
        time.sleep(1)
    except Exception as e:
        print(f"{C_DANGER}[!] Erreur lors du dechiffrement : {e}{C_END}")
        time.sleep(4)

def list_backup_contents(current_admin):
    all_backups = glob.glob(os.path.join(BACKUP_DATA_DIR, "*.zip.enc"))
    if not all_backups:
        print(f"{C_DANGER}[!] Aucune archive trouvee.{C_END}")
        time.sleep(2)
        return

    print(f"\n{C_BASE}=== INSPECTION DES ARCHIVES ==={C_END}")
    for i, path in enumerate(all_backups):
        size = os.path.getsize(path) / (1024 * 1024)
        print(f"{i+1}. {os.path.basename(path)} ({size:.2f} Mo)")
    
    print("0. Annuler")
    
    try:
        c = input("\nQuelle archive inspecter ? (Numero) : ").strip()
        if c == '0' or c == '':
            return
            
        c = int(c)
        if 1 <= c <= len(all_backups):
            target_enc = all_backups[c-1]
            
            print(f"{C_WARN}[*] Lecture securisee de l'archive en memoire vive...{C_END}")
            with open(target_enc, "rb") as f:
                encrypted_data = f.read()
            
            decrypted_data = cipher.decrypt(encrypted_data)
            
            with zipfile.ZipFile(io.BytesIO(decrypted_data)) as z:
                files = z.namelist()
            
            clear_screen()
            print(f"{C_BASE}=== CONTENU DE L'ARCHIVE : {os.path.basename(target_enc)} ==={C_END}\n")
            
            for f_name in files[:50]:
                if f_name.endswith('/'):
                    print(f"{C_BASE}[DOSSIER]{C_END} {f_name}")
                else:
                    print(f"{C_OK}[FICHIER]{C_END} {f_name}")
            
            if len(files) > 50:
                print(f"\n{C_WARN}... et {len(files) - 50} autres fichiers/dossiers masques pour la lisibilite.{C_END}")
            
            print(f"\n{C_OK}[+] Total : {len(files)} elements dans la sauvegarde.{C_END}")
            logging.info(f"[BACKUP] [{current_admin}] a consulte le contenu de {os.path.basename(target_enc)}")
            input("\nAppuyez sur Entree pour continuer...")
        else:
            print(f"{C_DANGER}Choix invalide.{C_END}")
            time.sleep(1)
    except ValueError:
        print(f"{C_DANGER}Entree invalide.{C_END}")
        time.sleep(1)
    except Exception as e:
        print(f"{C_DANGER}[!] Erreur lors de la lecture : {e}{C_END}")
        time.sleep(4)

def compute_crc32(file_path):
    hash_crc = 0
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_crc = zlib.crc32(chunk, hash_crc)
    except Exception:
        return None
    return hash_crc & 0xFFFFFFFF

def restore_backup(current_admin):
    all_backups = glob.glob(os.path.join(BACKUP_DATA_DIR, "*.zip.enc"))
    if not all_backups:
        print(f"{C_DANGER}[!] Aucune archive trouvee.{C_END}")
        time.sleep(2)
        return

    print(f"\n{C_DANGER}=== RESTAURATION DU SYSTEME (SMART ROLLBACK) ==={C_END}")
    print(f"{C_WARN}ATTENTION : Seuls les fichiers modifies ou supprimes seront restaures.{C_END}\n")
    
    for i, path in enumerate(all_backups):
        date_str = datetime.fromtimestamp(os.path.getctime(path)).strftime('%d/%m/%Y %H:%M')
        print(f"{i+1}. {os.path.basename(path)} (Creee le {date_str})")
    
    print("0. Annuler")
    
    try:
        c = input("\nArchive a restaurer ? (Numero) : ").strip()
        if c == '0' or c == '':
            return
            
        c = int(c)
        if 1 <= c <= len(all_backups):
            target_enc = all_backups[c-1]
            confirm = input(f"{C_DANGER}Etes-vous ABSOLUMENT SUR de vouloir restaurer {os.path.basename(target_enc)} ? (oui/non) : {C_END}").strip().lower()
            
            if confirm != 'oui':
                print(f"{C_WARN}Restauration annulee.{C_END}")
                time.sleep(2)
                return
            
            print(f"{C_WARN}[*] Dechiffrement et analyse intelligente des fichiers en cours...{C_END}")
            target_dir = ROOT_BACKUP_DIR
            
            with open(target_enc, "rb") as f:
                encrypted_data = f.read()
            
            decrypted_data = cipher.decrypt(encrypted_data)
            
            files_restored = 0
            files_skipped = 0

            with zipfile.ZipFile(io.BytesIO(decrypted_data)) as z:
                for zip_info in z.infolist():
                    target_path = os.path.join(target_dir, zip_info.filename)
                    
                    if zip_info.is_dir():
                        os.makedirs(target_path, exist_ok=True)
                        continue
                        
                    if os.path.exists(target_path):
                        local_crc = compute_crc32(target_path)
                        if local_crc == zip_info.CRC:
                            files_skipped += 1
                            continue 
                            
                        try:
                            os.chmod(target_path, stat.S_IWRITE)
                        except:
                            pass
                            
                    try:
                        z.extract(zip_info, target_dir)
                        files_restored += 1
                    except Exception as e:
                        print(f"{C_DANGER}Erreur sur {zip_info.filename} : {e}{C_END}")
                
            print(f"\n{C_OK}[+] SYSTEME RESTAURE AVEC SUCCES.{C_END}")
            print(f"{C_BASE}[i] Rapport Smart Restore : {files_restored} fichiers restaures, {files_skipped} fichiers ignores (deja a jour).{C_END}")
            logging.critical(f"[BACKUP] [{current_admin}] a effectue un SMART ROLLBACK depuis l'archive {os.path.basename(target_enc)}")
            input("\nAppuyez sur Entree pour continuer...")
        else:
            print(f"{C_DANGER}Choix invalide.{C_END}")
            time.sleep(1)
    except Exception as e:
        print(f"{C_DANGER}Erreur critique lors de la restauration : {e}{C_END}")
        time.sleep(4)

def manual_delete_backup(current_admin):
    enc_backups = glob.glob(os.path.join(BACKUP_DATA_DIR, "*.zip.enc"))
    raw_backups = glob.glob(os.path.join(BACKUP_DATA_DIR, "*.zip"))
    all_backups = enc_backups + raw_backups
    all_backups.sort(key=os.path.getctime)

    if not all_backups:
        print(f"{C_DANGER}[!] Aucune archive trouvee.{C_END}")
        time.sleep(2)
        return

    print(f"\n{C_DANGER}=== SUPPRESSION MANUELLE ==={C_END}")
    for i, path in enumerate(all_backups):
        print(f"{i+1}. {os.path.basename(path)}")
    
    print("0. Annuler")
    
    try:
        c = input("\nArchive a supprimer ? (Numero) : ").strip()
        if c == '0' or c == '':
            return
            
        c = int(c)
        if 1 <= c <= len(all_backups):
            target = all_backups[c-1]
            
            confirm = input(f"{C_WARN}Etes-vous sur de vouloir supprimer {os.path.basename(target)} ? (oui/non) : {C_END}").strip().lower()
            
            if confirm == 'oui':
                os.remove(target)
                print(f"{C_OK}[+] L'archive {os.path.basename(target)} a ete supprimee.{C_END}")
                logging.warning(f"[BACKUP] [{current_admin}] a SUPPRIME l'archive {os.path.basename(target)}")
                time.sleep(2)
            else:
                print(f"{C_WARN}Suppression annulee.{C_END}")
                time.sleep(2)
        else:
            print(f"{C_DANGER}Choix invalide.{C_END}")
            time.sleep(1)
    except Exception as e:
        print(f"{C_DANGER}Erreur : {e}{C_END}")
        time.sleep(2)

def view_backup_logs(current_admin):
    clear_screen()
    print(f"{C_BASE}=== LOGS DU GESTIONNAIRE DE SAUVEGARDE ==={C_END}\n")
    if os.path.exists(log_file):
        logs_to_show = []
        with open(log_file, 'r') as f:
            for line in f:
                if "[BACKUP]" in line:
                    logs_to_show.append(line.strip())
        
        if logs_to_show:
            for line in logs_to_show[-25:]:
                print(line)
        else:
            print(f"{C_WARN}Aucune action de sauvegarde enregistree pour le moment.{C_END}")
    else:
        print(f"{C_DANGER}Fichier de log introuvable.{C_END}")
    
    logging.info(f"[BACKUP] [{current_admin}] a consulte les logs de sauvegarde.")
    input("\nAppuyez sur Entree pour revenir.")

def open_backup_menu(current_admin):
    clear_screen() 
    print(f"\n{C_DANGER}=== ZONE SECURISEE : GESTION DES SAUVEGARDES ==={C_END}")
    pwd = getpass.getpass("Veuillez confirmer votre mot de passe : ").strip()
    
    try:
        with DBLock(USER_DATA_PATH):
            verify_and_restore_integrity(USER_DATA_PATH)
            with open(USER_DATA_PATH, 'r') as f:
                users = json.load(f)
    except Exception as e:
        print(f"{C_DANGER}Erreur de lecture du fichier JSON : {e}{C_END}")
        time.sleep(2)
        return

    stored_admin_hash = users[current_admin].get("password", "").encode('utf-8')
    try:
        admin_match = bcrypt.checkpw(pwd.encode('utf-8'), stored_admin_hash)
    except ValueError:
        admin_match = False

    if not admin_match:
        print(f"{C_DANGER}[!] Echec de l'authentification. Retour au menu principal.{C_END}")
        logging.warning(f"Tentative ECHOUEE acces menu Backup par: {current_admin}")
        time.sleep(2)
        return

    logging.info(f"Acces REUSSI menu Backup par: {current_admin}")
    
    while True:
        clear_screen()
        print(f"{C_BASE}=== GESTION DES SAUVEGARDES (Admin: {current_admin}) ==={C_END}\n")
        
        config = load_backup_config()
        all_backups = glob.glob(os.path.join(BACKUP_DATA_DIR, "*.zip.enc"))
        if all_backups:
            latest = max(all_backups, key=os.path.getctime)
            date_str = datetime.fromtimestamp(os.path.getctime(latest)).strftime('%d/%m/%Y %H:%M')
            print(f"{C_OK}[ STATUT : Dernier backup le {date_str} ]{C_END}\n")
        else:
            print(f"{C_DANGER}[ STATUT : AUCUNE SAUVEGARDE EXISTANTE ]{C_END}\n")

        unite_aff = "jours" if config['interval_type'] == "days" else "heures"

        print(f"{C_BASE}--- MENU ---{C_END}")
        print(f"1. {C_OK}Lancer un Full Backup manuel{C_END}")
        print(f"2. {C_DANGER}Restaurer une sauvegarde (Rollback System){C_END}")
        print(f"3. {C_BASE}Inspecter le contenu d'une archive (RAM){C_END}")
        print(f"4. {C_WARN}Dechiffrer une archive vers WinRAR (Extraction){C_END}")
        print(f"5. {C_DANGER}Supprimer une archive manuellement{C_END}")
        print(f"6. {C_BASE}Consulter les logs de sauvegarde{C_END}")
        print(f"7. {C_WARN}Configurer la planification{C_END} (Actuel: Tous les {config['interval_value']} {unite_aff})")
        print(f"8. {C_WARN}Configurer la retention{C_END} (Actuel: Garde {config['retention_count']} fichiers)")
        print("0. Retour au menu principal")
        
        choix = input("\nAction : ").strip()
        
        if choix == "1":
            run_full_backup(current_admin, silent=False)
        elif choix == "2":
            restore_backup(current_admin)
        elif choix == "3":
            list_backup_contents(current_admin)
        elif choix == "4":
            decrypt_existing_backup(current_admin)
        elif choix == "5":
            manual_delete_backup(current_admin)
        elif choix == "6":
            view_backup_logs(current_admin)
        elif choix == "7":
            t = input("Unite de temps (jours/heures) : ").strip().lower()
            if t in ["jours", "heures"]:
                v = input(f"Nombre de {t} : ")
                if v.isdigit():
                    config["interval_type"] = "days" if t == "jours" else "hours"
                    config["interval_value"] = int(v)
                    save_backup_config(config)
                    print(f"{C_OK}Configuration sauvegardee.{C_END}")
                    time.sleep(1)
            else:
                print(f"{C_DANGER}Unite invalide.{C_END}")
                time.sleep(1)
        elif choix == "8":
            v = input("Nombre maximum de backups a conserver (min 1) : ")
            if v.isdigit() and int(v) >= 1:
                config["retention_count"] = int(v)
                save_backup_config(config)
                print(f"{C_OK}Retention mise a jour.{C_END}")
                time.sleep(1)
            else:
                print(f"{C_DANGER}Valeur invalide (doit etre superieure ou egale a 1).{C_END}")
                time.sleep(2)
        elif choix == "0" or choix == "":
            break

def authenticate():
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    while True:
        clear_screen()
        print(f"{C_WARN}*** ACCES RESTREINT : AUTHENTIFICATION REQUISE ***{C_END}")
        print(f"Connexion a la Master Console.\n")
        
        user = input("Identifiant : ").strip().lower()
        if not user:
            continue
            
        pwd_input = getpass.getpass("Mot de passe : ").strip()
        print()
        
        try:
            with DBLock(USER_DATA_PATH):
                verify_and_restore_integrity(USER_DATA_PATH)
                with open(USER_DATA_PATH, 'r') as f:
                    valid_users = json.load(f)
        except Exception as e:
            print(f"{C_DANGER}[!] ERREUR 100 : Impossible de lire la base. Details: {e}{C_END}")
            time.sleep(4)
            return None, None

        user_exists = user in valid_users
        stored_hash = valid_users.get(user, {}).get("password", "").encode('utf-8') if user_exists else bcrypt.hashpw(b"dummy", bcrypt.gensalt())
        
        try:
            password_match = bcrypt.checkpw(pwd_input.encode('utf-8'), stored_hash)
        except ValueError:
            password_match = False

        if not user_exists:
            print(f"{C_DANGER}[!] ERREUR 200 : Identifiants incorrects.{C_END}")
            time.sleep(2)
            continue

        user_data = valid_users[user]
        current_time = time.time()
        lock_until = user_data.get("lock_until", 0)
        
        if current_time < lock_until:
            display_lockout_screen(lock_until)
            continue

        if not password_match:
            failed_attempts = user_data.get("failed_attempts", 0) + 1
            if failed_attempts >= 3 and failed_attempts % 3 == 0:
                multiplier = 2 ** ((failed_attempts // 3) - 1)
                lock_duration = 60 * multiplier
                lock_until_new = current_time + lock_duration
                safe_update_user(USER_DATA_PATH, user, {"failed_attempts": failed_attempts, "lock_until": lock_until_new})
                logging.warning(f"[ALERTE] Compte {user} verrouille pour {lock_duration}s (Tentatives: {failed_attempts})")
                display_lockout_screen(lock_until_new)
                continue
            else:
                safe_update_user(USER_DATA_PATH, user, {"failed_attempts": failed_attempts})
                print(f"{C_DANGER}[!] ERREUR 200 : Identifiants incorrects.{C_END}")
                logging.warning(f"Tentative ECHOUEE pour: {user}")
                time.sleep(2)
                continue

        if user_data.get("blocked", False):
            print(f"{C_DANGER}[!] ERREUR 403 : Ce compte a ete suspendu par un administrateur.{C_END}")
            time.sleep(4)
            return None, None

        failed_count = user_data.get("failed_attempts", 0)

        if failed_count > SEUIL_CRITIQUE:
            print(f"\n{C_DANGER}[!] ALERTE MAXIMALE : {failed_count} TENTATIVES ECHOUEES DETECTEES [!]{C_END}")
            print(f"{C_WARN}Par mesure de precaution, vous devez obligatoirement changer votre mot de passe.{C_END}\n")
            logging.critical(f"[SECURITE] Reinitialisation forcee apres {failed_count} echecs pour {user}")
            time.sleep(3)
            safe_update_user(USER_DATA_PATH, user, {"force_reset": True})
            user_data["force_reset"] = True

        elif SEUIL_AVERTISSEMENT <= failed_count <= SEUIL_CRITIQUE:
            print(f"\n{C_DANGER}==================================================={C_END}")
            print(f"{C_DANGER}[!] AVERTISSEMENT DE SECURITE [!]{C_END}")
            print(f"{C_WARN}Le systeme a detecte {failed_count} tentative(s) de connexion echouee(s){C_END}")
            print(f"{C_WARN}sur votre identifiant depuis votre derniere session.{C_END}")
            print(f"{C_DANGER}==================================================={C_END}\n")
            logging.info(f"Notification de {failed_count} echecs precedents pour {user}")
            
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
                        dec = decrypt_val(user_data[k])
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
                        safe_update_user(USER_DATA_PATH, user, {"force_reset": True})
                        user_data["force_reset"] = True
                    else:
                        print(f"{C_DANGER}[!] ERREUR : IDENTITE NON CONFIRMEE.{C_END}")
                        print(f"{C_WARN}La session va etre interrompue pour des raisons de securite.{C_END}") 
                        logging.warning(f"Echec de verification d'identite pour {user}")
                        time.sleep(3)
                        return None, None
                else:
                    print(f"{C_WARN}[!] Aucune information de profil disponible pour la verification.{C_END}")
                    print(f"{C_WARN}Par mesure de precaution absolue, vous devez modifier votre mot de passe.{C_END}")
                    safe_update_user(USER_DATA_PATH, user, {"force_reset": True})
                    user_data["force_reset"] = True

        if failed_count > 0:
            safe_update_user(USER_DATA_PATH, user, {"failed_attempts": 0, "lock_until": 0})

        if user_data.get("force_reset"):
            print(f"\n{C_WARN}[!] MISE A JOUR DE SECURITE REQUISE.{C_END}")
            print(f"Vous devez obligatoirement modifier votre mot de passe.\n")
            while True:
                new_pwd = getpass.getpass("\nNouveau mot de passe : ").strip()
                if not new_pwd:
                    continue
                missing = check_password_complexity(new_pwd)
                if missing:
                    print(f"{C_DANGER}Mot de passe invalide. Il manque : {', '.join(missing)}{C_END}")
                    continue
                
                confirm = getpass.getpass("Confirmez le mot de passe : ").strip()
                if new_pwd != confirm:
                    print(f"{C_DANGER}Les mots de passe ne correspondent pas. Reessayez.{C_END}")
                    continue
                
                try:
                    if bcrypt.checkpw(new_pwd.encode('utf-8'), stored_hash):
                        print(f"{C_DANGER}Le nouveau mot de passe doit etre different de l'ancien.{C_END}")
                        continue
                except ValueError: pass
                
                new_hashed = bcrypt.hashpw(new_pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                break

            try:
                safe_update_user(USER_DATA_PATH, user, {
                    "password": new_hashed,
                    "force_reset": False,
                    "reset_by_admin": False
                })
                print(f"{C_OK}[+] Mot de passe mis a jour avec succes.{C_END}")
                logging.info(f"Mot de passe reinitialise avec succes par {user}")
                time.sleep(2)
            except Exception as e:
                print(f"{C_DANGER}Erreur lors de la sauvegarde : {e}{C_END}")
                time.sleep(3)
                return None, None

        role = user_data.get("role", "user")
        logging.info(f"Connexion REUSSIE Utilisateur: {user} | Role: {role}")
        return user, role

def manage_users(current_admin):
    while True:
        clear_screen()
        print(f"{C_BASE}*** GESTION DES UTILISATEURS (Admin: {current_admin}) ***{C_END}\n")
        
        try:
            with DBLock(USER_DATA_PATH):
                verify_and_restore_integrity(USER_DATA_PATH)
                with open(USER_DATA_PATH, 'r') as f: 
                    users = json.load(f)
        except Exception as e:
            print(f"{C_DANGER}Erreur de lecture du fichier JSON : {e}{C_END}")
            time.sleep(3)
            break

        print(f"{'Utilisateur':<15} | {'Role':<10} | {'Reset':<5} | {'Bloque':<6}")
        print("*" * 50)
        for u, data in users.items():
            needs_reset = "Oui" if data.get("force_reset") else "Non"
            is_blocked = "Oui" if data.get("blocked") else "Non"
            c_bloc = C_DANGER if is_blocked == "Oui" else C_END
            print(f"{u:<15} | {data.get('role', 'user'):<10} | {needs_reset:<5} | {c_bloc}{is_blocked:<6}{C_END}")
        
        print(f"\n1. {C_OK}Ajouter un utilisateur{C_END}")
        print(f"2. {C_DANGER}Supprimer un utilisateur{C_END}")
        print(f"3. {C_WARN}Inspecter / Modifier un utilisateur{C_END}")
        print("0. Retour")
        
        choice = input("\nAction : ").strip()
        if choice == '0' or choice == '': 
            break

        if choice in ['1', '2', '3']:
            clear_screen()
            if choice == '1': 
                print(f"{C_OK}*** AJOUTER UN NOUVEL UTILISATEUR ***{C_END}\n")
            elif choice == '2': 
                print(f"{C_DANGER}*** SUPPRIMER UN UTILISATEUR ***{C_END}\n")
            elif choice == '3': 
                print(f"{C_WARN}*** INSPECTER / MODIFIER UN UTILISATEUR ***{C_END}\n")

            print(f"{C_WARN}Pour des raisons de securite liees aux donnees personnelles, veuillez vous authentifier.{C_END}")
            admin_pwd = getpass.getpass(f"Mot de passe de {current_admin} (ou '0' pour annuler) : ").strip()
            
            if admin_pwd == '0' or admin_pwd == '': 
                print(f"\n{C_WARN}Action annulee.{C_END}")
                time.sleep(2)
                continue
            
            stored_admin_hash = users[current_admin].get("password", "").encode('utf-8')
            try:
                admin_match = bcrypt.checkpw(admin_pwd.encode('utf-8'), stored_admin_hash)
            except ValueError:
                admin_match = False
                
            if not admin_match:
                print(f"{C_DANGER}[!] Mot de passe incorrect.{C_END}")
                time.sleep(2)
                continue

            if choice == '1':
                nom = ""
                while not nom:
                    nom = input("\n1. Nom de famille ['0' annuler] : ").strip().upper()
                if nom == '0': 
                    print(f"\n{C_WARN}Action annulee.{C_END}")
                    time.sleep(2)
                    continue
                
                prenom = ""
                while not prenom:
                    prenom = input("2. Prenom ['0' annuler] : ").strip().capitalize()
                if prenom == '0': 
                    print(f"\n{C_WARN}Action annulee.{C_END}")
                    time.sleep(2)
                    continue

                new_user = ""
                while True:
                    new_user = input("3. Nom d'utilisateur (login) ['0' annuler] : ").strip().lower()
                    if new_user == '0': 
                        break
                    if not new_user or new_user in users:
                        print(f"{C_DANGER}Identifiant invalide ou deja existant.{C_END}")
                        continue
                    break
                if new_user == '0': 
                    print(f"\n{C_WARN}Action annulee.{C_END}")
                    time.sleep(2)
                    continue

                email_in = ""
                while True:
                    email_in = input("4. Email (vide pour ignorer) ['0' annuler] : ").strip()
                    if email_in in ['0', '']: 
                        break
                    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email_in):
                        print(f"{C_DANGER}Format d'email invalide.{C_END}")
                        continue
                    if not is_unique(users, "email", email_in):
                        print(f"{C_DANGER}Cet email est deja utilise par un autre compte.{C_END}")
                        continue
                    break
                if email_in == '0': 
                    print(f"\n{C_WARN}Action annulee.{C_END}")
                    time.sleep(2)
                    continue

                phone_in = ""
                while True:
                    print("5. Telephone (vide pour ignorer) ['0' annuler]")
                    c_code = input("   Pays (ex: FR, 'liste' pour voir, vide pour ignorer) : ").strip().lower()
                    if c_code == '0': 
                        phone_in = '0'
                        break
                    if c_code == '': 
                        break
                    
                    if c_code == 'liste':
                        for k, v in COUNTRIES.items(): 
                            print(f"   - {k.upper()} : {v['name']} ({v['code']})")
                        continue
                        
                    if c_code not in COUNTRIES:
                        print(f"{C_DANGER}Pays inconnu. Tapez 'liste' pour voir les choix.{C_END}")
                        continue
                        
                    country = COUNTRIES[c_code]
                    num = input(f"   Numero {country['code']} : ").strip()
                    if num == '0': 
                        phone_in = '0'
                        break
                    
                    num = num.replace(" ", "").replace(".", "").replace("-", "")
                    if num.startswith(country['code']): 
                        num = num[len(country['code']):]
                    if num.startswith('0'): 
                        num = num[1:] 
                    
                    if len(num) != country['len']:
                        print(f"{C_DANGER}Longueur invalide. Attente de {country['len']} chiffres apres le {country['code']}.{C_END}")
                        continue
                        
                    full_phone = country['code'] + num
                    if not is_unique(users, "phone", full_phone):
                        print(f"{C_DANGER}Ce numero est deja utilise.{C_END}")
                        continue
                        
                    phone_in = full_phone
                    break
                if phone_in == '0': 
                    print(f"\n{C_WARN}Action annulee.{C_END}")
                    time.sleep(2)
                    continue

                print("\n*** Informations Professionnelles ***")
                entreprise = input("6. Entreprise (vide pour ignorer) : ").strip()
                secteur = input("7. Secteur (vide pour ignorer) : ").strip()
                poste = input("8. Nom du poste (vide pour ignorer) : ").strip()

                pwd_choice = ""
                while True:
                    print("\n9. Configuration du mot de passe :")
                    print("   1. Taper manuellement")
                    print("   2. Generer automatiquement")
                    print("   0. Annuler")
                    pwd_choice = input("   Choix : ").strip()
                    if pwd_choice in ['0', '1', '2']: 
                        break
                    print(f"{C_DANGER}Choix invalide.{C_END}")
                if pwd_choice == '0': 
                    print(f"\n{C_WARN}Action annulee.{C_END}")
                    time.sleep(2)
                    continue

                new_pwd = ""
                if pwd_choice == '2':
                    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
                    while True:
                        new_pwd = ''.join(secrets.choice(alphabet) for i in range(12))
                        if not check_password_complexity(new_pwd): 
                            break
                    print(f"\n{C_OK}Mot de passe genere : {new_pwd}{C_END}")
                    print(f"{C_WARN}ATTENTION : Notez-le, il ne s'affichera plus !{C_END}")
                    input("Appuyez sur Entree quand vous l'avez note...")
                    sys.stdout.write("\033[4A\033[J")
                    sys.stdout.flush()
                    print(f"\n{C_OK}Mot de passe genere : [MASQUE PAR SECURITE]{C_END}\n")
                else:
                    cancel_pwd = False
                    while True:
                        new_pwd = getpass.getpass("\nMot de passe temporaire ('0' pour annuler) : ").strip()
                        if new_pwd == '0' or new_pwd == '': 
                            cancel_pwd = True
                            break
                        missing = check_password_complexity(new_pwd)
                        if missing:
                            print(f"{C_DANGER}Mot de passe invalide. Manque : {', '.join(missing)}{C_END}")
                            continue
                        confirm = getpass.getpass("Confirmez : ").strip()
                        if new_pwd != confirm:
                            print(f"{C_DANGER}Correspondance echouee.{C_END}")
                            continue
                        break
                    if cancel_pwd: 
                        print(f"\n{C_WARN}Action annulee.{C_END}")
                        time.sleep(2)
                        continue

                new_role = ""
                while True:
                    new_role = input("10. Role (admin/moniteur/user) ['0' annuler] : ").strip().lower()
                    if new_role == '0': 
                        break
                    if new_role not in ['admin', 'user', 'moniteur', '']:
                        print(f"{C_WARN}Role non reconnu.{C_END}")
                        continue
                    if new_role == '': 
                        new_role = 'user'
                    break
                if new_role == '0': 
                    print(f"\n{C_WARN}Action annulee.{C_END}")
                    time.sleep(2)
                    continue

                hashed = bcrypt.hashpw(new_pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

                try:
                    with DBLock(USER_DATA_PATH):
                        verify_and_restore_integrity(USER_DATA_PATH)
                        with open(USER_DATA_PATH, 'r') as f: 
                            fresh_users = json.load(f)
                        fresh_users[new_user] = {
                            "id": str(uuid.uuid4()),
                            "blocked": False,
                            "password": hashed,
                            "role": new_role,
                            "force_reset": True,
                            "reset_by_admin": False,
                            "nom": encrypt_val(nom),
                            "prenom": encrypt_val(prenom),
                            "email": encrypt_val(email_in if email_in else "Non renseigne"),
                            "phone": encrypt_val(phone_in if phone_in else "Non renseigne"),
                            "entreprise": encrypt_val(entreprise if entreprise else "Non renseigne"),
                            "secteur": encrypt_val(secteur if secteur else "Non renseigne"),
                            "poste": encrypt_val(poste if poste else "Non renseigne")
                        }
                        atomic_update_database(USER_DATA_PATH, fresh_users)
                    print(f"\n{C_OK}[+] Utilisateur '{new_user}' cree avec succes.{C_END}")
                    logging.info(f"Creation compte: {new_user} par {current_admin}")
                except Exception as e:
                    print(f"\n{C_DANGER}Erreur BDD : {e}{C_END}")
                time.sleep(2)

            elif choice == '2':
                del_user = input("Identifiant de l'utilisateur a supprimer (ou '0' pour annuler) : ").strip().lower()
                if del_user == '0' or del_user == '': 
                    print(f"\n{C_WARN}Action annulee.{C_END}")
                    time.sleep(2)
                    continue
                if del_user == current_admin: 
                    print(f"{C_DANGER}Impossible de supprimer votre propre compte !{C_END}")
                    time.sleep(3)
                    continue
                if del_user not in users: 
                    print(f"{C_WARN}Utilisateur introuvable.{C_END}")
                    time.sleep(2)
                    continue
                
                confirm = input(f"\n{C_DANGER}ATTENTION : Etes-vous sur de vouloir supprimer definitivement '{del_user}' ? (o/n) : {C_END}").strip().lower()
                if confirm != 'o':
                    print(f"\n{C_WARN}Suppression annulee.{C_END}")
                    time.sleep(2)
                    continue

                try:
                    with DBLock(USER_DATA_PATH):
                        verify_and_restore_integrity(USER_DATA_PATH)
                        with open(USER_DATA_PATH, 'r') as f: 
                            fresh_users = json.load(f)
                        if del_user in fresh_users:
                            del fresh_users[del_user]
                            atomic_update_database(USER_DATA_PATH, fresh_users)
                            print(f"{C_OK}[-] Utilisateur '{del_user}' supprime.{C_END}")
                            logging.warning(f"Suppression du compte {del_user} par {current_admin}")
                        else:
                            print(f"{C_WARN}Deja supprime par un autre processus.{C_END}")
                except Exception as e: 
                    print(f"{C_DANGER}Erreur BDD : {e}{C_END}")
                time.sleep(2)

            elif choice == '3':
                target = input("Identifiant a inspecter (ou '0' pour annuler) : ").strip().lower()
                if target == '0' or target == '': 
                    print(f"\n{C_WARN}Action annulee.{C_END}")
                    time.sleep(2)
                    continue
                if target not in users: 
                    print(f"{C_WARN}Utilisateur introuvable.{C_END}")
                    time.sleep(2)
                    continue
                
                while True:
                    try:
                        with DBLock(USER_DATA_PATH):
                            verify_and_restore_integrity(USER_DATA_PATH)
                            with open(USER_DATA_PATH, 'r') as f: 
                                fresh_users = json.load(f)
                    except Exception as e: 
                        print(f"{C_DANGER}Erreur de lecture : {e}{C_END}")
                        time.sleep(3)
                        break

                    if target not in fresh_users:
                        print(f"{C_DANGER}L'utilisateur a ete supprime entre temps.{C_END}")
                        time.sleep(3)
                        break

                    u_data = fresh_users[target]
                    clear_screen()
                    print(f"{C_BASE}=== PROFIL DE {target.upper()} ==={C_END}\n")
                    print(f"ID Unique  : {C_BASE}{u_data.get('id', 'N/A')}{C_END}")
                    print(f"Statut     : {C_DANGER + 'BLOQUE' + C_END if u_data.get('blocked') else C_OK + 'ACTIF' + C_END}")
                    print(f"Role       : {u_data.get('role', 'user')}")
                    print(f"Reset req. : {'Oui' if u_data.get('force_reset') else 'Non'}")
                    print(f"Nom        : {decrypt_val(u_data.get('nom', ''))}")
                    print(f"Prenom     : {decrypt_val(u_data.get('prenom', ''))}")
                    print(f"Email      : {decrypt_val(u_data.get('email', ''))}")
                    print(f"Telephone  : {decrypt_val(u_data.get('phone', ''))}")
                    print(f"Entreprise : {decrypt_val(u_data.get('entreprise', ''))}")
                    print(f"Secteur    : {decrypt_val(u_data.get('secteur', ''))}")
                    print(f"Poste      : {decrypt_val(u_data.get('poste', ''))}")
                    
                    print(f"\n{C_OK}*** GESTION ET MODIFICATION ***{C_END}")
                    print("1. Modifier Email")
                    print("2. Modifier Telephone")
                    print("3. Modifier Informations Pro")
                    print(f"4. {C_WARN}Reinitialiser le mot de passe (Genere un temp){C_END}")
                    print(f"5. {C_WARN}Forcer la modification du mot de passe (En cas de fuite){C_END}")
                    print(f"6. {C_DANGER}Bloquer / Debloquer l'acces du compte{C_END}")
                    print("0. Retour au menu gestion")
                    
                    mod_choice = input("\nChoix : ").strip()
                    if mod_choice == '0' or mod_choice == '': 
                        break
                    
                    field_updates = {}
                    
                    if mod_choice == '1':
                        em = input("Nouvel Email (vide pour vider) : ").strip()
                        if em and not re.match(r"^[^@]+@[^@]+\.[^@]+$", em):
                            print(f"{C_DANGER}Format invalide.{C_END}")
                            time.sleep(2)
                            continue
                        if em and not is_unique(fresh_users, "email", em):
                            print(f"{C_DANGER}Email deja utilise.{C_END}")
                            time.sleep(2)
                            continue
                        field_updates["email"] = encrypt_val(em if em else "Non renseigne")
                        logging.info(f"[{current_admin}] a modifie l'email de {target}")
                        
                    elif mod_choice == '2':
                        c_code = input("Code pays (ex: FR, 'liste' pour voir, vide pour vider) : ").strip().lower()
                        if not c_code: 
                            field_updates["phone"] = encrypt_val("Non renseigne")
                        else:
                            if c_code == 'liste':
                                for k, v in COUNTRIES.items(): 
                                    print(f"   - {k.upper()} : {v['name']} ({v['code']})")
                                input("Appuyez sur Entree...")
                                continue
                            if c_code not in COUNTRIES:
                                print(f"{C_DANGER}Pays inconnu.{C_END}")
                                time.sleep(2)
                                continue
                            country = COUNTRIES[c_code]
                            num = input(f"Numero {country['code']} : ").strip()
                            num = num.replace(" ", "").replace(".", "").replace("-", "")
                            if num.startswith(country['code']): 
                                num = num[len(country['code']):]
                            if num.startswith('0'): 
                                num = num[1:]
                            if len(num) != country['len']:
                                print(f"{C_DANGER}Taille invalide pour {c_code.upper()}.{C_END}")
                                time.sleep(2)
                                continue
                            full = country['code'] + num
                            if not is_unique(fresh_users, "phone", full):
                                print(f"{C_DANGER}Numero deja utilise.{C_END}")
                                time.sleep(2)
                                continue
                            field_updates["phone"] = encrypt_val(full)
                            logging.info(f"[{current_admin}] a modifie le telephone de {target}")
                            
                    elif mod_choice == '3':
                        ent = input("Entreprise (vide=conserver, 'vider'=effacer) : ").strip()
                        sec = input("Secteur (vide=conserver, 'vider'=effacer) : ").strip()
                        pos = input("Poste (vide=conserver, 'vider'=effacer) : ").strip()
                        if ent: 
                            field_updates["entreprise"] = encrypt_val("Non renseigne" if ent.lower() == 'vider' else ent)
                        if sec: 
                            field_updates["secteur"] = encrypt_val("Non renseigne" if sec.lower() == 'vider' else sec)
                        if pos: 
                            field_updates["poste"] = encrypt_val("Non renseigne" if pos.lower() == 'vider' else pos)
                        logging.info(f"[{current_admin}] a modifie les infos pro de {target}")

                    elif mod_choice == '4':
                        print("\n4. Reinitialiser le mot de passe :")
                        print("   1. Taper manuellement")
                        print("   2. Generer automatiquement")
                        print("   0. Annuler")
                        pwd_c = input("   Choix : ").strip()
                        if pwd_c not in ['1', '2']: 
                            continue
                        
                        new_pwd = ""
                        if pwd_c == '2':
                            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
                            while True:
                                new_pwd = ''.join(secrets.choice(alphabet) for i in range(12))
                                if not check_password_complexity(new_pwd): 
                                    break
                            print(f"\n{C_OK}Nouveau mot de passe de {target} : {new_pwd}{C_END}")
                            input("Notez-le et donnez-le a l'utilisateur. Appuyez sur Entree...")
                            sys.stdout.write("\033[3A\033[J")
                            sys.stdout.flush()
                            print(f"\n{C_OK}Mot de passe genere : [MASQUE PAR SECURITE]{C_END}\n")
                        else:
                            cancel_pwd = False
                            while True:
                                new_pwd = getpass.getpass("\nNouveau MDP temporaire ('0' pour annuler) : ").strip()
                                if new_pwd == '0' or new_pwd == '': 
                                    cancel_pwd = True
                                    break
                                missing = check_password_complexity(new_pwd)
                                if missing: 
                                    print(f"{C_DANGER}Mot de passe invalide. Manque : {', '.join(missing)}{C_END}")
                                    continue
                                confirm = getpass.getpass("Confirmez : ").strip()
                                if new_pwd != confirm: 
                                    print(f"{C_DANGER}Correspondance echouee.{C_END}")
                                    continue
                                break
                            if cancel_pwd: 
                                continue
                            
                        field_updates["password"] = bcrypt.hashpw(new_pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        field_updates["force_reset"] = True
                        field_updates["reset_by_admin"] = True
                        logging.warning(f"[{current_admin}] a REINITIALISE le mot de passe de {target}")

                    elif mod_choice == '5':
                        field_updates["force_reset"] = True
                        logging.warning(f"[{current_admin}] a force le changement de mot de passe (fuite) pour {target}")

                    elif mod_choice == '6':
                        if target == current_admin:
                            print(f"{C_DANGER}Impossible de bloquer votre propre compte.{C_END}")
                            time.sleep(2)
                            continue
                        
                        current_status = u_data.get("blocked", False)
                        field_updates["blocked"] = not current_status
                        status_str = "BLOQUE" if not current_status else "DEBLOQUE"
                        logging.warning(f"[{current_admin}] a {status_str} l'acces de {target}")

                    if field_updates:
                        try:
                            safe_update_user(USER_DATA_PATH, target, field_updates)
                            print(f"{C_OK}[+] Action appliquee avec succes sur {target}.{C_END}")
                            time.sleep(2)
                        except Exception as e: 
                            print(f"{C_DANGER}Erreur de sauvegarde : {e}{C_END}")
                            time.sleep(3)

        elif choice == '0':
            break

def capture_container_logs(container, q_out, proc_list):
    proc = subprocess.Popen(["docker", "logs", "-f", "--tail=20", container], 
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    proc_list.append(proc)
    try:
        for line in iter(proc.stdout.readline, ''):
            if line: 
                q_out.put(f"{C_BASE}[{container}]{C_END} {line.strip()}")
    except: 
        pass

def menu_actions(targets, current_user, current_role):
    while True:
        if not is_docker_alive(): 
            return
        clear_screen()
        print(f"{C_BASE}=== CIBLES : {', '.join(targets)} | Operateur : {current_user} ({current_role.upper()}) ==={C_END}\n")
        
        print(f"1. {C_OK}Console SSH (1ere cible){C_END}")
        
        if current_role == "admin":
            print(f"2. {C_DANGER}Hard Crash (Stop){C_END}")
            print(f"3. {C_OK}Power On (Start){C_END}")
            print(f"4. {C_BASE}Logiciels et Attaques{C_END}")
            
        print("0. Retour")
        
        c = input(f"\nChoix : ").strip()
        
        if c == '1':
            m = targets[0]
            if is_container_running(m):
                logging.info(f"[{current_user}] Ouverture d'une session SSH vers {m}")
                os.system('clear')
                os.system(f"docker exec -it {m} python3 /scripts/internal_login.py")
                logging.info(f"[{current_user}] Fermeture de la session SSH vers {m}")
            else:
                print(f"{C_WARN}[!] Machine eteinte.{C_END}")
                time.sleep(2)
                
        elif c == '2':
            if current_role != "admin": 
                continue
            clear_screen()
            print(f"{C_DANGER}=== DESACTIVATION EN COURS ==={C_END}\n")
            states = {m: f"{C_BASE}En attente...{C_END}" for m in targets}
            for _ in targets: 
                print()
            def render_states_stop():
                sys.stdout.write(f"\033[{len(targets)}A")
                for m in targets: 
                    sys.stdout.write(f"[*] {m} : {states[m]}\033[K\n")
                sys.stdout.flush()
            render_states_stop()
            for m in targets:
                states[m] = f"{C_WARN}Desactivation en cours...{C_END}"
                render_states_stop()
                run(f"docker stop {m}")
                states[m] = f"{C_DANGER}Desactivee.{C_END}"
                render_states_stop()
            print(f"\n{C_OK}[OK] Toutes les cibles selectionnees sont stoppees.{C_END}")
            time.sleep(2)
            break
            
        elif c == '3':
            if current_role != "admin": 
                continue
            clear_screen()
            print(f"{C_OK}=== DEMARRAGE EN COURS ==={C_END}\n")
            states = {m: f"{C_BASE}En attente...{C_END}" for m in targets}
            for _ in targets: 
                print()
            def render_states_start():
                sys.stdout.write(f"\033[{len(targets)}A")
                for m in targets: 
                    sys.stdout.write(f"[*] {m} : {states[m]}\033[K\n")
                sys.stdout.flush()
            render_states_start()
            for m in targets:
                states[m] = f"{C_WARN}Demarrage en cours...{C_END}"
                render_states_start()
                run(f"docker start {m}")
                states[m] = f"{C_OK}En ligne.{C_END}"
                render_states_start()
            print(f"\n{C_OK}[OK] Toutes les cibles selectionnees sont demarrees.{C_END}")
            time.sleep(2)
            break
            
        elif c == '4':
            if current_role != "admin": 
                continue
            clear_screen()
            print(f"{C_BASE}=== PREPARATION DES ATTAQUES ==={C_END}\n")
            online_machines = [m for m in targets if is_container_running(m)]
            offline_machines = [m for m in targets if not is_container_running(m)]
            if offline_machines:
                print(f"{C_WARN}[!] Info : Eteintes (ignorees) : {', '.join(offline_machines)}{C_END}")
            if not online_machines:
                print(f"\n{C_DANGER}[!] Erreur : Aucune machine allumee.{C_END}")
                time.sleep(3)
                break
            print(f"\n{C_BASE}*** LOGICIELS ***{C_END}")
            print("1. Ouvrir Chrome  2. Fermer Chrome")
            print(f"\n{C_DANGER}*** MALWARES ET ATTAQUES ***{C_END}")
            print("3. Mineur Crypto  4. Ransomware     5. Attaque DDoS")
            print(f"\n{C_OK}*** MAINTENANCE ET DEFENSE ***{C_END}")
            print("6. Antivirus      7. Regles Firewall (Stop DDoS)  8. Nettoyage")
            print("\n0. Annuler")
            sub = input("\nAction : ").strip()
            map_a = {"1":"open_chrome", "2":"close_chrome", "3":"virus_on", "4":"ransomware", "5":"ddos", "6":"virus_off", "7":"ddos_off", "8":"clean"}
            act = map_a.get(sub)
            if act:
                for m in online_machines:
                    run(f"docker exec {m} python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:5000/trigger?action={act}')\"")
                print(f"{C_OK}[OK] Ordre execute.{C_END}")
                time.sleep(2)
            break
            
        elif c == '0' or c == '': 
            break

def main():
    patch_database()

    while True:
        current_user, current_role = authenticate()
        if not current_user: 
            sys.exit(1)
        print(f"{C_OK}[*] Authentification validee. Bienvenue {current_user} ! (Role: {current_role}){C_END}")
        time.sleep(1)
        
        if current_role == "admin":
            check_auto_backup()
            
        while True:
            clear_screen()
            if not is_docker_alive():
                print(f"{C_DANGER}ERREUR : DOCKER OFFLINE{C_END}")
                time.sleep(3)
                continue

            m_list = get_machines()
            print(f"{C_BASE}=========================================={C_END}")
            print(f"{C_BASE}       CYBER MONITOR : MASTER CONSOLE     {C_END}")
            print(f"{C_WARN}       Session Active : {current_user.upper()} [{current_role.upper()}] {C_END}")
            print(f"{C_BASE}=========================================={C_END}\n")
            
            for i, m in enumerate(m_list):
                col = C_OK if "Up" in m['status'] else C_DANGER
                print(f"{i+1}. {m['name']} {col}[{m['status']}]{C_END}")
            
            if current_role == "admin":
                print(f"\n{C_BASE}Commandes : Numeros (ex: 1,2), 'toutes', 'L' (Logs), 'U' (Utilisateurs), 'B' (Backups), 'P' (Mon Profil), 'D' (Deconnexion), 'Q' (Quitter){C_END}")
            elif current_role in ["moniteur", "monitoring"]:
                print(f"\n{C_BASE}Commandes : Numeros (ex: 1,2), 'toutes', 'L' (Logs), 'P' (Mon Profil), 'D' (Deconnexion), 'Q' (Quitter){C_END}")
            else:
                print(f"\n{C_BASE}Commandes : Numeros (ex: 1,2), 'toutes', 'P' (Mon Profil), 'D' (Deconnexion), 'Q' (Quitter){C_END}")
                
            choice = input(f"\n{C_WARN}Selection : {C_END}").lower().strip()
            
            if choice == 'q':
                print(f"\n{C_OK}Fermeture de la Master Console. Au revoir {current_user} !{C_END}")
                sys.exit(0)
            if choice == 'd':
                print(f"\n{C_WARN}Deconnexion...{C_END}")
                time.sleep(2)
                break 
            if choice == 'p':
                manage_own_profile(current_user)
                continue
            if choice == 'u' and current_role == 'admin':
                manage_users(current_user)
                continue
            if choice == 'b' and current_role == 'admin':
                open_backup_menu(current_user)
                continue

            if choice == 'l':
                if current_role == "user":
                    print(f"\n{C_DANGER}[!] Acces refuse.{C_END}")
                    time.sleep(2)
                    continue
                print(f"\n{C_BASE}Quelles machines monitorer ? (ex: 1,2 ou toutes){C_END}")
                log_choice = input(f"{C_WARN}Cibles : {C_END}").lower().strip()
                selected_logs = []
                if log_choice in ['toutes', 'all', '*']: 
                    selected_logs = [m['name'] for m in m_list]
                else:
                    try:
                        raw = log_choice.replace(' ', ',')
                        indexes = [int(x) - 1 for x in raw.split(',') if x.isdigit()]
                        selected_logs = [m_list[i]['name'] for i in indexes if 0 <= i < len(m_list)]
                    except: 
                        continue
                
                if not selected_logs: 
                    continue
                online_logs = [m for m in selected_logs if is_container_running(m)]
                offline_logs = [m for m in selected_logs if not is_container_running(m)]

                if not online_logs:
                    print(f"{C_DANGER}[!] Erreur : Aucune machine allumee.{C_END}")
                    time.sleep(3)
                    continue

                clear_screen()
                print(f"{C_BASE}=== LOGS EN DIRECT : {', '.join(online_logs)} ==={C_END}\n")
                
                q = queue.Queue()
                procs = []
                for m_name in online_logs:
                    threading.Thread(target=capture_container_logs, args=(m_name, q, procs), daemon=True).start()

                msg = f"{C_WARN}>>> [Q] RETOUR MENU <<<{C_END}"
                if offline_logs: 
                    msg += f"  {C_DANGER}[Masquees car Eteintes : {', '.join(offline_logs)}]{C_END}"
                sys.stdout.write(msg)
                sys.stdout.flush()

                def refresh_screen(new_log=None, clear=False):
                    cols = shutil.get_terminal_size((80, 20)).columns
                    plain_msg = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', msg)
                    lines_occupied = max(1, (len(plain_msg) // cols) + 1)
                    sys.stdout.write("\r")
                    if lines_occupied > 1: 
                        sys.stdout.write(f"\033[{lines_occupied - 1}A")
                    sys.stdout.write("\033[J")
                    if not clear:
                        if new_log: 
                            sys.stdout.write(new_log + "\n")
                        sys.stdout.write(msg)
                    sys.stdout.flush()

                if os.name == 'nt':
                    import msvcrt
                    try:
                        while True:
                            if msvcrt.kbhit() and msvcrt.getch().lower() == b'q': 
                                break
                            while not q.empty(): 
                                refresh_screen(q.get_nowait())
                            time.sleep(0.05)
                    except KeyboardInterrupt: 
                        pass
                else:
                    import select
                    try:
                        while True:
                            while not q.empty(): 
                                refresh_screen(q.get_nowait())
                            if sys.stdin in select.select([sys.stdin], [], [], 0.05)[0]:
                                if sys.stdin.read(1).lower() == 'q': 
                                    break
                    except KeyboardInterrupt: 
                        pass
                
                for p in procs:
                    try: 
                        p.terminate()
                    except: 
                        pass
                refresh_screen(clear=True)
                continue

            selected = []
            if choice in ['toutes', 'all', '*']: 
                selected = [m['name'] for m in m_list]
            else:
                try:
                    raw = choice.replace(' ', ',')
                    indexes = [int(x) - 1 for x in raw.split(',') if x.isdigit()]
                    selected = [m_list[i]['name'] for i in indexes if 0 <= i < len(m_list)]
                except: 
                    continue
            
            if selected: 
                menu_actions(selected, current_user, current_role)

if __name__ == "__main__":
    try: 
        main()
    except KeyboardInterrupt: 
        print(f"\n\n{C_OK}Master Console arretee brutalement. Au revoir !{C_END}")
        sys.exit(0)