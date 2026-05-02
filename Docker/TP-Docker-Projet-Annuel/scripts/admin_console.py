import os
import subprocess
import time
import sys
import threading
import queue
import getpass
import hashlib
import shutil
import re
import json
import logging
import secrets
import string
import uuid
from cryptography.fernet import Fernet

# *** CONFIGURATION DES LOGS ***
current_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.normpath(os.path.join(current_dir, "..", "..", "..", "Data", "Logs"))
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "Logs_Console_Admin.log")

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# *** CHIFFREMENT (FERNET) ***
SECRET_KEY = b"1fRmwCnDxGocFZciu2YKqeOD_BtSuj4rkqtH3-nhHuQ="
try:
    cipher = Fernet(SECRET_KEY)
except Exception as e:
    print(f"Erreur fatale de chiffrement (Clef invalide) : {e}")
    sys.exit(1)

def encrypt_val(val):
    if not val or val == "Non renseigne": return "Non renseigne"
    return cipher.encrypt(val.encode('utf-8')).decode('utf-8')

def decrypt_val(val):
    if not val or val == "Non renseigne": return "Non renseigne"
    try:
        return cipher.decrypt(val.encode('utf-8')).decode('utf-8')
    except:
        return "[Erreur Dechiffrement]"

# *** DESIGN ***
C_BASE = '\033[96m'
C_OK = '\033[92m'
C_WARN = '\033[93m'
C_DANGER = '\033[91m'
C_END = '\033[0m'

USER_DATA_PATH = os.path.normpath(os.path.join(current_dir, "..", "..", "..", "Data", "Users", "users_docker.json"))

# *** DICTIONNAIRE TELEPHONIQUE ***
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
            if self.fd: os.close(self.fd)
            os.remove(self.lockfile)
        except Exception: pass

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def run(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.returncode
    except: return "", 1

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
    if not value or value == "Non renseigne": return True
    for u, data in users.items():
        if field in data and decrypt_val(data[field]) == value:
            return False
    return True

# *** PATCH DE LA BASE DE DONNEES ***
def patch_database():
    try:
        if not os.path.exists(USER_DATA_PATH): return
        with DBLock(USER_DATA_PATH):
            with open(USER_DATA_PATH, 'r') as f: users = json.load(f)
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
                with open(USER_DATA_PATH, 'w') as f: json.dump(users, f, indent=4)
                logging.info("Mise a jour de la base de donnees (Patch UUID, blocked, force_reset, reset_by_admin).")
    except Exception as e:
        logging.error(f"Erreur lors du patch de la BDD : {e}")

def authenticate():
    for attempt in range(3, 0, -1):
        clear_screen()
        print(f"{C_WARN}*** ACCES RESTREINT : AUTHENTIFICATION REQUISE ***{C_END}")
        print(f"Connexion a la Master Console.\n")
        
        user = input("Identifiant : ").strip().lower()
        pwd = getpass.getpass("Mot de passe : ").strip()
        
        print()
        
        try:
            with DBLock(USER_DATA_PATH):
                with open(USER_DATA_PATH, 'r') as f:
                    valid_users = json.load(f)
        except Exception as e:
            print(f"{C_DANGER}[!] ERREUR 100 : Impossible de lire la base. Details: {e}{C_END}"); time.sleep(4); return None, None
        
        hashed_pwd = hashlib.sha256(pwd.encode('utf-8')).hexdigest()

        if user not in valid_users or valid_users[user].get("password") != hashed_pwd:
            if user in valid_users and valid_users[user].get("reset_by_admin"):
                print(f"{C_DANGER}[!] ACCES REFUSE : Votre mot de passe a ete reinitialise.{C_END}")
                print(f"{C_WARN}Veuillez contacter l'administrateur ou le support IT pour obtenir votre mot de passe temporaire.{C_END}")
                time.sleep(4)
            else:
                print(f"{C_DANGER}[!] ERREUR 200 : Identifiants incorrects.{C_END}")
            
            logging.warning(f"Tentative ECHOUEE (200) Identifiants incorrects pour: {user}")
            if attempt > 1:
                print(f"{C_WARN}Il vous reste {attempt - 1} essai(s).{C_END}"); time.sleep(2); continue
            else:
                print(f"{C_DANGER}[!] ACCES REFUSE. Incident enregistre.{C_END}"); time.sleep(3); return None, None

        if valid_users[user].get("blocked", False):
            print(f"{C_DANGER}[!] ERREUR 403 : Ce compte a ete suspendu par un administrateur.{C_END}")
            logging.warning(f"Tentative de connexion bloquee (Compte suspendu) pour : {user}")
            time.sleep(4)
            return None, None

        if valid_users[user].get("force_reset"):
            print(f"\n{C_WARN}[!] PREMIERE CONNEXION OU FUITE : Vous devez modifier votre mot de passe.{C_END}")
            while True:
                new_pwd = getpass.getpass("\nNouveau mot de passe : ").strip()
                missing = check_password_complexity(new_pwd)
                if missing:
                    print(f"{C_DANGER}Mot de passe invalide. Il manque : {', '.join(missing)}{C_END}"); continue
                
                confirm = getpass.getpass("Confirmez le mot de passe : ").strip()
                if new_pwd != confirm:
                    print(f"{C_DANGER}Les mots de passe ne correspondent pas. Reessayez.{C_END}"); continue
                
                new_hashed = hashlib.sha256(new_pwd.encode('utf-8')).hexdigest()
                if new_hashed == hashed_pwd:
                    print(f"{C_DANGER}Le nouveau mot de passe doit etre different de l'ancien.{C_END}"); continue
                break

            try:
                with DBLock(USER_DATA_PATH):
                    with open(USER_DATA_PATH, 'r') as f: fresh_users = json.load(f)
                    fresh_users[user]["password"] = new_hashed
                    fresh_users[user]["force_reset"] = False
                    fresh_users[user]["reset_by_admin"] = False
                    with open(USER_DATA_PATH, 'w') as f: json.dump(fresh_users, f, indent=4)
                print(f"{C_OK}[+] Mot de passe mis a jour avec succes.{C_END}"); time.sleep(2)
            except Exception as e:
                print(f"{C_DANGER}Erreur lors de la sauvegarde : {e}{C_END}"); time.sleep(3); return None, None

        role = valid_users[user].get("role", "user")
        logging.info(f"Connexion REUSSIE Utilisateur: {user} | Role: {role}")
        return user, role

def manage_users(current_admin):
    while True:
        clear_screen()
        print(f"{C_BASE}*** GESTION DES UTILISATEURS (Admin: {current_admin}) ***{C_END}\n")
        
        try:
            with DBLock(USER_DATA_PATH):
                with open(USER_DATA_PATH, 'r') as f: users = json.load(f)
        except Exception as e:
            print(f"{C_DANGER}Erreur de lecture du fichier JSON : {e}{C_END}"); time.sleep(3); break

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
        if choice == '0': break

        if choice in ['1', '2', '3']:
            clear_screen()
            if choice == '1': print(f"{C_OK}*** AJOUTER UN NOUVEL UTILISATEUR ***{C_END}\n")
            elif choice == '2': print(f"{C_DANGER}*** SUPPRIMER UN UTILISATEUR ***{C_END}\n")
            elif choice == '3': print(f"{C_WARN}*** INSPECTER / MODIFIER UN UTILISATEUR ***{C_END}\n")

            print(f"{C_WARN}Pour des raisons de securite liees aux donnees personnelles, veuillez vous authentifier.{C_END}")
            admin_pwd = getpass.getpass(f"Mot de passe de {current_admin} (ou '0' pour annuler) : ").strip()
            
            if admin_pwd == '0': print(f"\n{C_WARN}Action annulee.{C_END}"); time.sleep(2); continue
            if hashlib.sha256(admin_pwd.encode('utf-8')).hexdigest() != users[current_admin].get("password"):
                print(f"{C_DANGER}[!] Mot de passe incorrect.{C_END}"); time.sleep(2); continue

            # === AJOUT ===
            if choice == '1':
                nom = ""
                while not nom:
                    nom = input("\n1. Nom de famille ['0' annuler] : ").strip().upper()
                if nom == '0': print(f"\n{C_WARN}Action annulee.{C_END}"); time.sleep(2); continue
                
                prenom = ""
                while not prenom:
                    prenom = input("2. Prenom ['0' annuler] : ").strip().capitalize()
                if prenom == '0': print(f"\n{C_WARN}Action annulee.{C_END}"); time.sleep(2); continue

                new_user = ""
                while True:
                    new_user = input("3. Nom d'utilisateur (login) ['0' annuler] : ").strip().lower()
                    if new_user == '0': break
                    if not new_user or new_user in users:
                        print(f"{C_DANGER}Identifiant invalide ou deja existant.{C_END}"); continue
                    break
                if new_user == '0': print(f"\n{C_WARN}Action annulee.{C_END}"); time.sleep(2); continue

                email_in = ""
                while True:
                    email_in = input("4. Email (vide pour ignorer) ['0' annuler] : ").strip()
                    if email_in in ['0', '']: break
                    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email_in):
                        print(f"{C_DANGER}Format d'email invalide.{C_END}"); continue
                    if not is_unique(users, "email", email_in):
                        print(f"{C_DANGER}Cet email est deja utilise par un autre compte.{C_END}"); continue
                    break
                if email_in == '0': print(f"\n{C_WARN}Action annulee.{C_END}"); time.sleep(2); continue

                phone_in = ""
                while True:
                    print("5. Telephone (vide pour ignorer) ['0' annuler]")
                    c_code = input("   Pays (ex: FR, 'liste' pour voir, vide pour ignorer) : ").strip().lower()
                    if c_code == '0': phone_in = '0'; break
                    if c_code == '': break
                    
                    if c_code == 'liste':
                        for k, v in COUNTRIES.items(): print(f"   - {k.upper()} : {v['name']} ({v['code']})")
                        continue
                        
                    if c_code not in COUNTRIES:
                        print(f"{C_DANGER}Pays inconnu. Tapez 'liste' pour voir les choix.{C_END}"); continue
                        
                    country = COUNTRIES[c_code]
                    num = input(f"   Numero {country['code']} : ").strip()
                    if num == '0': phone_in = '0'; break
                    
                    num = num.replace(" ", "").replace(".", "").replace("-", "")
                    if num.startswith(country['code']): num = num[len(country['code']):]
                    if num.startswith('0'): num = num[1:] 
                    
                    if len(num) != country['len']:
                        print(f"{C_DANGER}Longueur invalide. Attente de {country['len']} chiffres apres le {country['code']} (sans zero).{C_END}")
                        continue
                        
                    full_phone = country['code'] + num
                    if not is_unique(users, "phone", full_phone):
                        print(f"{C_DANGER}Ce numero est deja utilise.{C_END}"); continue
                        
                    phone_in = full_phone
                    break
                if phone_in == '0': print(f"\n{C_WARN}Action annulee.{C_END}"); time.sleep(2); continue

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
                    if pwd_choice in ['0', '1', '2']: break
                    print(f"{C_DANGER}Choix invalide.{C_END}")
                if pwd_choice == '0': print(f"\n{C_WARN}Action annulee.{C_END}"); time.sleep(2); continue

                new_pwd = ""
                if pwd_choice == '2':
                    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
                    while True:
                        new_pwd = ''.join(secrets.choice(alphabet) for i in range(12))
                        if not check_password_complexity(new_pwd): break
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
                        if new_pwd == '0': cancel_pwd = True; break
                        missing = check_password_complexity(new_pwd)
                        if missing:
                            print(f"{C_DANGER}Mot de passe invalide. Manque : {', '.join(missing)}{C_END}"); continue
                        confirm = getpass.getpass("Confirmez : ").strip()
                        if new_pwd != confirm:
                            print(f"{C_DANGER}Correspondance echouee.{C_END}"); continue
                        break
                    if cancel_pwd: print(f"\n{C_WARN}Action annulee.{C_END}"); time.sleep(2); continue

                new_role = ""
                while True:
                    new_role = input("10. Role (admin/moniteur/user) ['0' annuler] : ").strip().lower()
                    if new_role == '0': break
                    if new_role not in ['admin', 'user', 'moniteur', '']:
                        print(f"{C_WARN}Role non reconnu.{C_END}"); continue
                    if new_role == '': new_role = 'user'
                    break
                if new_role == '0': print(f"\n{C_WARN}Action annulee.{C_END}"); time.sleep(2); continue

                hashed = hashlib.sha256(new_pwd.encode('utf-8')).hexdigest()

                try:
                    with DBLock(USER_DATA_PATH):
                        with open(USER_DATA_PATH, 'r') as f: fresh_users = json.load(f)
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
                        with open(USER_DATA_PATH, 'w') as f: json.dump(fresh_users, f, indent=4)
                    print(f"\n{C_OK}[+] Utilisateur '{new_user}' cree avec succes.{C_END}")
                    logging.info(f"Creation compte: {new_user} par {current_admin}")
                except Exception as e:
                    print(f"\n{C_DANGER}Erreur BDD : {e}{C_END}")
                time.sleep(2)

            # === SUPPRESSION ===
            elif choice == '2':
                del_user = input("Identifiant de l'utilisateur a supprimer (ou '0' pour annuler) : ").strip().lower()
                if del_user == '0': print(f"\n{C_WARN}Action annulee.{C_END}"); time.sleep(2); continue
                if del_user == current_admin: print(f"{C_DANGER}Impossible de supprimer votre propre compte !{C_END}"); time.sleep(3); continue
                if del_user not in users: print(f"{C_WARN}Utilisateur introuvable.{C_END}"); time.sleep(2); continue
                
                confirm = input(f"\n{C_DANGER}ATTENTION : Etes-vous sur de vouloir supprimer definitivement '{del_user}' ? (o/n) : {C_END}").strip().lower()
                if confirm != 'o':
                    print(f"\n{C_WARN}Suppression annulee.{C_END}"); time.sleep(2); continue

                try:
                    with DBLock(USER_DATA_PATH):
                        with open(USER_DATA_PATH, 'r') as f: fresh_users = json.load(f)
                        if del_user in fresh_users:
                            del fresh_users[del_user]
                            with open(USER_DATA_PATH, 'w') as f: json.dump(fresh_users, f, indent=4)
                            print(f"{C_OK}[-] Utilisateur '{del_user}' supprime.{C_END}")
                            logging.warning(f"Suppression du compte {del_user} par {current_admin}")
                        else:
                            print(f"{C_WARN}Deja supprime par un autre processus.{C_END}")
                except Exception as e: print(f"{C_DANGER}Erreur BDD : {e}{C_END}")
                time.sleep(2)

            # === INSPECTION / MODIFICATION ===
            elif choice == '3':
                target = input("Identifiant a inspecter (ou '0' pour annuler) : ").strip().lower()
                if target == '0': print(f"\n{C_WARN}Action annulee.{C_END}"); time.sleep(2); continue
                if target not in users: print(f"{C_WARN}Utilisateur introuvable.{C_END}"); time.sleep(2); continue
                
                while True:
                    try:
                        with DBLock(USER_DATA_PATH):
                            with open(USER_DATA_PATH, 'r') as f: fresh_users = json.load(f)
                    except Exception as e: print(f"{C_DANGER}Erreur de lecture : {e}{C_END}"); time.sleep(3); break

                    if target not in fresh_users:
                        print(f"{C_DANGER}L'utilisateur a ete supprime entre temps.{C_END}"); time.sleep(3); break

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
                    if mod_choice == '0': break
                    
                    field_updates = {}
                    
                    if mod_choice == '1':
                        em = input("Nouvel Email (vide pour vider) : ").strip()
                        if em and not re.match(r"^[^@]+@[^@]+\.[^@]+$", em):
                            print(f"{C_DANGER}Format invalide.{C_END}"); time.sleep(2); continue
                        if em and not is_unique(fresh_users, "email", em):
                            print(f"{C_DANGER}Email deja utilise.{C_END}"); time.sleep(2); continue
                        field_updates["email"] = encrypt_val(em if em else "Non renseigne")
                        logging.info(f"[{current_admin}] a modifie l'email de {target}")
                        
                    elif mod_choice == '2':
                        c_code = input("Code pays (ex: FR, 'liste' pour voir, vide pour vider) : ").strip().lower()
                        if not c_code: field_updates["phone"] = encrypt_val("Non renseigne")
                        else:
                            if c_code == 'liste':
                                for k, v in COUNTRIES.items(): print(f"   - {k.upper()} : {v['name']} ({v['code']})")
                                input("Appuyez sur Entree..."); continue
                            if c_code not in COUNTRIES:
                                print(f"{C_DANGER}Pays inconnu.{C_END}"); time.sleep(2); continue
                            country = COUNTRIES[c_code]
                            num = input(f"Numero {country['code']} : ").strip()
                            num = num.replace(" ", "").replace(".", "").replace("-", "")
                            if num.startswith(country['code']): num = num[len(country['code']):]
                            if num.startswith('0'): num = num[1:]
                            if len(num) != country['len']:
                                print(f"{C_DANGER}Taille invalide pour {c_code.upper()}.{C_END}"); time.sleep(2); continue
                            full = country['code'] + num
                            if not is_unique(fresh_users, "phone", full):
                                print(f"{C_DANGER}Numero deja utilise.{C_END}"); time.sleep(2); continue
                            field_updates["phone"] = encrypt_val(full)
                            logging.info(f"[{current_admin}] a modifie le telephone de {target}")
                            
                    elif mod_choice == '3':
                        ent = input("Entreprise (vide=conserver, 'vider'=effacer) : ").strip()
                        sec = input("Secteur (vide=conserver, 'vider'=effacer) : ").strip()
                        pos = input("Poste (vide=conserver, 'vider'=effacer) : ").strip()
                        if ent: field_updates["entreprise"] = encrypt_val("Non renseigne" if ent.lower() == 'vider' else ent)
                        if sec: field_updates["secteur"] = encrypt_val("Non renseigne" if sec.lower() == 'vider' else sec)
                        if pos: field_updates["poste"] = encrypt_val("Non renseigne" if pos.lower() == 'vider' else pos)
                        logging.info(f"[{current_admin}] a modifie les infos pro de {target}")

                    elif mod_choice == '4':
                        print("\n4. Reinitialiser le mot de passe :")
                        print("   1. Taper manuellement")
                        print("   2. Generer automatiquement")
                        print("   0. Annuler")
                        pwd_c = input("   Choix : ").strip()
                        if pwd_c not in ['1', '2']: continue
                        
                        new_pwd = ""
                        if pwd_c == '2':
                            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
                            while True:
                                new_pwd = ''.join(secrets.choice(alphabet) for i in range(12))
                                if not check_password_complexity(new_pwd): break
                            print(f"\n{C_OK}Nouveau mot de passe de {target} : {new_pwd}{C_END}")
                            input("Notez-le et donnez-le a l'utilisateur. Appuyez sur Entree...")
                            sys.stdout.write("\033[3A\033[J")
                            sys.stdout.flush()
                            print(f"\n{C_OK}Mot de passe genere : [MASQUE PAR SECURITE]{C_END}\n")
                        else:
                            cancel_pwd = False
                            while True:
                                new_pwd = getpass.getpass("\nNouveau MDP temporaire ('0' pour annuler) : ").strip()
                                if new_pwd == '0': cancel_pwd = True; break
                                missing = check_password_complexity(new_pwd)
                                if missing: print(f"{C_DANGER}Mot de passe invalide. Manque : {', '.join(missing)}{C_END}"); continue
                                confirm = getpass.getpass("Confirmez : ").strip()
                                if new_pwd != confirm: print(f"{C_DANGER}Correspondance echouee.{C_END}"); continue
                                break
                            if cancel_pwd: continue
                            
                        field_updates["password"] = hashlib.sha256(new_pwd.encode('utf-8')).hexdigest()
                        field_updates["force_reset"] = True
                        field_updates["reset_by_admin"] = True
                        logging.warning(f"[{current_admin}] a REINITIALISE le mot de passe de {target}")

                    elif mod_choice == '5':
                        field_updates["force_reset"] = True
                        logging.warning(f"[{current_admin}] a force le changement de mot de passe (fuite) pour {target}")

                    elif mod_choice == '6':
                        if target == current_admin:
                            print(f"{C_DANGER}Impossible de bloquer votre propre compte.{C_END}"); time.sleep(2); continue
                        
                        current_status = u_data.get("blocked", False)
                        field_updates["blocked"] = not current_status
                        status_str = "BLOQUE" if not current_status else "DEBLOQUE"
                        logging.warning(f"[{current_admin}] a {status_str} l'acces de {target}")

                    if field_updates:
                        try:
                            with DBLock(USER_DATA_PATH):
                                with open(USER_DATA_PATH, 'r') as f: sync_users = json.load(f)
                                for k, v in field_updates.items(): sync_users[target][k] = v
                                with open(USER_DATA_PATH, 'w') as f: json.dump(sync_users, f, indent=4)
                            print(f"{C_OK}[+] Action appliquee avec succes sur {target}.{C_END}"); time.sleep(2)
                        except Exception as e: print(f"{C_DANGER}Erreur de sauvegarde : {e}{C_END}"); time.sleep(3)

        elif choice == '0':
            break

def capture_container_logs(container, q_out, proc_list):
    proc = subprocess.Popen(["docker", "logs", "-f", "--tail=20", container], 
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    proc_list.append(proc)
    try:
        for line in iter(proc.stdout.readline, ''):
            if line: q_out.put(f"{C_BASE}[{container}]{C_END} {line.strip()}")
    except: pass

def menu_actions(targets, current_user, current_role):
    while True:
        if not is_docker_alive(): return
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
            if current_role != "admin": continue
            clear_screen()
            print(f"{C_DANGER}=== DESACTIVATION EN COURS ==={C_END}\n")
            states = {m: f"{C_BASE}En attente...{C_END}" for m in targets}
            for _ in targets: print()
            def render_states_stop():
                sys.stdout.write(f"\033[{len(targets)}A")
                for m in targets: sys.stdout.write(f"[*] {m} : {states[m]}\033[K\n")
                sys.stdout.flush()
            render_states_stop()
            for m in targets:
                states[m] = f"{C_WARN}Desactivation en cours...{C_END}"
                render_states_stop()
                run(f"docker stop {m}")
                states[m] = f"{C_DANGER}Desactivee.{C_END}"
                render_states_stop()
            print(f"\n{C_OK}[OK] Toutes les cibles selectionnees sont stoppees.{C_END}")
            time.sleep(2); break
            
        elif c == '3':
            if current_role != "admin": continue
            clear_screen()
            print(f"{C_OK}=== DEMARRAGE EN COURS ==={C_END}\n")
            states = {m: f"{C_BASE}En attente...{C_END}" for m in targets}
            for _ in targets: print()
            def render_states_start():
                sys.stdout.write(f"\033[{len(targets)}A")
                for m in targets: sys.stdout.write(f"[*] {m} : {states[m]}\033[K\n")
                sys.stdout.flush()
            render_states_start()
            for m in targets:
                states[m] = f"{C_WARN}Demarrage en cours...{C_END}"
                render_states_start()
                run(f"docker start {m}")
                states[m] = f"{C_OK}En ligne.{C_END}"
                render_states_start()
            print(f"\n{C_OK}[OK] Toutes les cibles selectionnees sont demarrees.{C_END}")
            time.sleep(2); break
            
        elif c == '4':
            if current_role != "admin": continue
            clear_screen()
            print(f"{C_BASE}=== PREPARATION DES ATTAQUES ==={C_END}\n")
            online_machines = [m for m in targets if is_container_running(m)]
            offline_machines = [m for m in targets if not is_container_running(m)]
            if offline_machines:
                print(f"{C_WARN}[!] Info : Eteintes (ignorees) : {', '.join(offline_machines)}{C_END}")
            if not online_machines:
                print(f"\n{C_DANGER}[!] Erreur : Aucune machine allumee.{C_END}")
                time.sleep(3); break
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
            
        elif c == '0': break

def main():
    patch_database()

    while True:
        current_user, current_role = authenticate()
        if not current_user: sys.exit(1)
        print(f"{C_OK}[*] Authentification validee. Bienvenue {current_user} ! (Role: {current_role}){C_END}")
        time.sleep(2)
            
        while True:
            clear_screen()
            if not is_docker_alive():
                print(f"{C_DANGER}ERREUR : DOCKER OFFLINE{C_END}"); time.sleep(3); continue

            m_list = get_machines()
            print(f"{C_BASE}=========================================={C_END}")
            print(f"{C_BASE}       CYBER MONITOR : MASTER CONSOLE     {C_END}")
            print(f"{C_WARN}       Session Active : {current_user.upper()} [{current_role.upper()}] {C_END}")
            print(f"{C_BASE}=========================================={C_END}\n")
            
            for i, m in enumerate(m_list):
                col = C_OK if "Up" in m['status'] else C_DANGER
                print(f"{i+1}. {m['name']} {col}[{m['status']}]{C_END}")
            
            if current_role == "admin":
                print(f"\n{C_BASE}Commandes : Numeros (ex: 1,2), 'toutes', 'L' (Logs), 'U' (Utilisateurs), 'D' (Deconnexion), 'Q' (Quitter){C_END}")
            elif current_role in ["moniteur", "monitoring"]:
                print(f"\n{C_BASE}Commandes : Numeros (ex: 1,2), 'toutes', 'L' (Logs), 'D' (Deconnexion), 'Q' (Quitter){C_END}")
            else:
                print(f"\n{C_BASE}Commandes : Numeros (ex: 1,2), 'toutes', 'D' (Deconnexion), 'Q' (Quitter){C_END}")
                
            choice = input(f"\n{C_WARN}Selection : {C_END}").lower().strip()
            
            if choice == 'q':
                print(f"\n{C_OK}Fermeture de la Master Console. Au revoir {current_user} !{C_END}"); sys.exit(0)
            if choice == 'd':
                print(f"\n{C_WARN}Deconnexion...{C_END}"); time.sleep(2); break 
            if choice == 'u' and current_role == 'admin':
                manage_users(current_user); continue

            if choice == 'l':
                if current_role == "user":
                    print(f"\n{C_DANGER}[!] Acces refuse.{C_END}"); time.sleep(2); continue
                print(f"\n{C_BASE}Quelles machines monitorer ? (ex: 1,2 ou toutes){C_END}")
                log_choice = input(f"{C_WARN}Cibles : {C_END}").lower().strip()
                selected_logs = []
                if log_choice in ['toutes', 'all', '*']: selected_logs = [m['name'] for m in m_list]
                else:
                    try:
                        raw = log_choice.replace(' ', ',')
                        indexes = [int(x) - 1 for x in raw.split(',') if x.isdigit()]
                        selected_logs = [m_list[i]['name'] for i in indexes if 0 <= i < len(m_list)]
                    except: continue
                
                if not selected_logs: continue
                online_logs = [m for m in selected_logs if is_container_running(m)]
                offline_logs = [m for m in selected_logs if not is_container_running(m)]

                if not online_logs:
                    print(f"{C_DANGER}[!] Erreur : Aucune machine allumee.{C_END}"); time.sleep(3); continue

                clear_screen()
                print(f"{C_BASE}=== LOGS EN DIRECT : {', '.join(online_logs)} ==={C_END}\n")
                
                q = queue.Queue()
                procs = []
                for m_name in online_logs:
                    threading.Thread(target=capture_container_logs, args=(m_name, q, procs), daemon=True).start()

                msg = f"{C_WARN}>>> [Q] RETOUR MENU <<<{C_END}"
                if offline_logs: msg += f"  {C_DANGER}[Masquees car Eteintes : {', '.join(offline_logs)}]{C_END}"
                sys.stdout.write(msg); sys.stdout.flush()

                def refresh_screen(new_log=None, clear=False):
                    cols = shutil.get_terminal_size((80, 20)).columns
                    plain_msg = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', msg)
                    lines_occupied = max(1, (len(plain_msg) // cols) + 1)
                    sys.stdout.write("\r")
                    if lines_occupied > 1: sys.stdout.write(f"\033[{lines_occupied - 1}A")
                    sys.stdout.write("\033[J")
                    if not clear:
                        if new_log: sys.stdout.write(new_log + "\n")
                        sys.stdout.write(msg)
                    sys.stdout.flush()

                if os.name == 'nt':
                    import msvcrt
                    try:
                        while True:
                            if msvcrt.kbhit() and msvcrt.getch().lower() == b'q': break
                            while not q.empty(): refresh_screen(q.get_nowait())
                            time.sleep(0.05)
                    except KeyboardInterrupt: pass
                else:
                    import select
                    try:
                        while True:
                            while not q.empty(): refresh_screen(q.get_nowait())
                            if sys.stdin in select.select([sys.stdin], [], [], 0.05)[0]:
                                if sys.stdin.read(1).lower() == 'q': break
                    except KeyboardInterrupt: pass
                
                for p in procs:
                    try: p.terminate()
                    except: pass
                refresh_screen(clear=True); continue

            selected = []
            if choice in ['toutes', 'all', '*']: selected = [m['name'] for m in m_list]
            else:
                try:
                    raw = choice.replace(' ', ',')
                    indexes = [int(x) - 1 for x in raw.split(',') if x.isdigit()]
                    selected = [m_list[i]['name'] for i in indexes if 0 <= i < len(m_list)]
                except: continue
            
            if selected: menu_actions(selected, current_user, current_role)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: 
        print(f"\n\n{C_OK}Master Console arretee brutalement. Au revoir !{C_END}"); sys.exit(0)