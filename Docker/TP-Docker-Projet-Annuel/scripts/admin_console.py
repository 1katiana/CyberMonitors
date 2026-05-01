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

# *** DESIGN ***
C_BASE = '\033[96m'
C_OK = '\033[92m'
C_WARN = '\033[93m'
C_DANGER = '\033[91m'
C_END = '\033[0m'

USER_DATA_PATH = os.path.normpath(os.path.join(current_dir, "..", "..", "..", "Data", "Users", "users_docker.json"))

# *** NOUVEAU : SYSTEME DE VERROU (MUTEX) POUR LE JSON ***
class DBLock:
    def __init__(self, path, timeout=5):
        self.lockfile = path + ".lock"
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                # O_CREAT | O_EXCL garantit une creation atomique. Echec si le fichier existe deja.
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
    if len(pwd) < 6:
        missing.append("6 caracteres minimum")
    if not any(c.isupper() for c in pwd):
        missing.append("une majuscule")
    if not any(c.islower() for c in pwd):
        missing.append("une minuscule")
    if not any(c.isdigit() for c in pwd):
        missing.append("un chiffre")
    if not any(c in string.punctuation for c in pwd):
        missing.append("un symbole specifique (!@#$%^&*...)")
    return missing

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
        except FileNotFoundError:
            print(f"{C_DANGER}[!] ERREUR 101 : Le fichier users_docker.json est introuvable.{C_END}")
            time.sleep(4)
            return None, None
        except Exception as e:
            print(f"{C_DANGER}[!] ERREUR 100 : Impossible de lire la base (Verrouillee ou corrompue). Details: {e}{C_END}")
            time.sleep(4)
            return None, None
        
        hashed_pwd = hashlib.sha256(pwd.encode('utf-8')).hexdigest()

        if user not in valid_users or valid_users[user].get("password") != hashed_pwd:
            print(f"{C_DANGER}[!] ERREUR 200 : Identifiants incorrects.{C_END}")
            logging.warning(f"Tentative ECHOUEE (200) Identifiants incorrects pour: {user}")
            if attempt > 1:
                print(f"{C_WARN}Il vous reste {attempt - 1} essai(s).{C_END}")
                time.sleep(2)
                continue
            else:
                print(f"{C_DANGER}[!] ACCES REFUSE. Incident de securite enregistre.{C_END}")
                time.sleep(2)
                return None, None

        if valid_users[user].get("force_reset"):
            print(f"\n{C_WARN}[!] PREMIERE CONNEXION : Vous devez modifier votre mot de passe.{C_END}")
            while True:
                new_pwd = getpass.getpass("\nNouveau mot de passe : ").strip()
                missing = check_password_complexity(new_pwd)
                if missing:
                    print(f"{C_DANGER}Mot de passe invalide. Il manque : {', '.join(missing)}{C_END}")
                    continue
                
                confirm = getpass.getpass("Confirmez le mot de passe : ").strip()
                if new_pwd != confirm:
                    print(f"{C_DANGER}Les mots de passe ne correspondent pas. Reessayez.{C_END}")
                    continue
                
                new_hashed = hashlib.sha256(new_pwd.encode('utf-8')).hexdigest()
                if new_hashed == hashed_pwd:
                    print(f"{C_DANGER}Le nouveau mot de passe doit etre different de l'ancien.{C_END}")
                    continue
                
                break

            try:
                # On reverrouille pour ecrire la modification de maniere securisee
                with DBLock(USER_DATA_PATH):
                    with open(USER_DATA_PATH, 'r') as f:
                        fresh_users = json.load(f)
                    
                    fresh_users[user]["password"] = new_hashed
                    fresh_users[user]["force_reset"] = False
                    
                    with open(USER_DATA_PATH, 'w') as f:
                        json.dump(fresh_users, f, indent=4)
                        
                print(f"{C_OK}[+] Mot de passe mis a jour avec succes.{C_END}")
                logging.info(f"[{user}] A mis a jour son mot de passe initial.")
                time.sleep(1.5)
            except Exception as e:
                print(f"{C_DANGER}Erreur lors de la sauvegarde : {e}{C_END}")
                time.sleep(3)
                return None, None

        role = valid_users[user].get("role", "user")
        logging.info(f"Connexion REUSSIE Utilisateur: {user} | Role: {role}")
        return user, role

def manage_users(current_admin):
    while True:
        clear_screen()
        print(f"{C_BASE}*** GESTION DES UTILISATEURS (Admin: {current_admin}) ***{C_END}\n")
        
        try:
            with DBLock(USER_DATA_PATH):
                with open(USER_DATA_PATH, 'r') as f:
                    users = json.load(f)
        except Exception as e:
            print(f"{C_DANGER}Erreur de lecture du fichier JSON (Base verrouillee) : {e}{C_END}")
            time.sleep(3)
            break

        print(f"{'Utilisateur':<15} | {'Role':<10} | {'Reset requis':<12}")
        print("*" * 45)
        for u, data in users.items():
            needs_reset = "Oui" if data.get("force_reset") else "Non"
            print(f"{u:<15} | {data.get('role', 'user'):<10} | {needs_reset:<12}")
        
        print(f"\n1. {C_OK}Ajouter un utilisateur{C_END}")
        print(f"2. {C_DANGER}Supprimer un utilisateur{C_END}")
        print("0. Retour")
        
        choice = input("\nAction : ").strip()

        if choice == '1':
            clear_screen()
            print(f"{C_OK}*** AJOUTER UN NOUVEL UTILISATEUR ***{C_END}\n")
            print(f"{C_WARN}Pour des raisons de securite, veuillez vous authentifier.{C_END}")
            admin_pwd = getpass.getpass(f"Mot de passe de {current_admin} (ou '0' pour annuler) : ").strip()
            
            if admin_pwd == '0':
                print(f"\n{C_WARN}Action annulee.{C_END}")
                time.sleep(1)
                continue

            admin_hash = hashlib.sha256(admin_pwd.encode('utf-8')).hexdigest()
            if admin_hash != users[current_admin].get("password"):
                print(f"{C_DANGER}[!] Mot de passe incorrect. Creation annulee.{C_END}")
                time.sleep(2)
                continue

            new_user = ""
            while True:
                new_user = input("\n1. Nom de l'utilisateur (ou '0' pour annuler) : ").strip().lower()
                if new_user == '0':
                    break
                if not new_user or new_user in users:
                    print(f"{C_WARN}Nom invalide ou utilisateur deja existant. Reessayez.{C_END}")
                    continue
                break
            
            if new_user == '0':
                print(f"\n{C_WARN}Action annulee.{C_END}")
                time.sleep(1)
                continue

            new_role = ""
            while True:
                new_role = input("\n2. Role (admin/moniteur/user) ['0' annuler] : ").strip().lower()
                if new_role == '0':
                    break
                if new_role not in ['admin', 'user', 'moniteur', '']:
                    print(f"{C_WARN}Role non reconnu. Veuillez choisir admin, moniteur ou user.{C_END}")
                    continue
                if new_role == '': 
                    new_role = 'user'
                break

            if new_role == '0':
                print(f"\n{C_WARN}Action annulee.{C_END}")
                time.sleep(1)
                continue

            pwd_choice = ""
            while True:
                print("\n3. Methodes de mot de passe :")
                print("   1. Taper manuellement")
                print("   2. Generer automatiquement")
                print("   0. Annuler")
                pwd_choice = input("Choix : ").strip()
                if pwd_choice in ['0', '1', '2']:
                    break
                print(f"{C_DANGER}Veuillez taper 0, 1 ou 2.{C_END}")

            if pwd_choice == '0':
                print(f"\n{C_WARN}Action annulee.{C_END}")
                time.sleep(1)
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
            else:
                cancel_pwd = False
                while True:
                    new_pwd = getpass.getpass("\nMot de passe temporaire ('0' pour annuler) : ").strip()
                    if new_pwd == '0':
                        cancel_pwd = True
                        break
                    
                    missing = check_password_complexity(new_pwd)
                    if missing:
                        print(f"{C_DANGER}Mot de passe invalide. Il manque : {', '.join(missing)}{C_END}")
                        continue
                    
                    confirm = getpass.getpass("Confirmez le mot de passe : ").strip()
                    if new_pwd != confirm:
                        print(f"{C_DANGER}Les mots de passe ne correspondent pas. Reessayez.{C_END}")
                        continue
                    break
                
                if cancel_pwd:
                    print(f"\n{C_WARN}Action annulee.{C_END}")
                    time.sleep(1)
                    continue

            hashed = hashlib.sha256(new_pwd.encode('utf-8')).hexdigest()

            try:
                # Verrouillage avant de finaliser l'ajout (au cas ou le fichier a change pendant la frappe)
                with DBLock(USER_DATA_PATH):
                    with open(USER_DATA_PATH, 'r') as f:
                        fresh_users = json.load(f)
                    fresh_users[new_user] = {"password": hashed, "role": new_role, "force_reset": True}
                    with open(USER_DATA_PATH, 'w') as f:
                        json.dump(fresh_users, f, indent=4)
                        
                print(f"\n{C_OK}[+] Utilisateur '{new_user}' cree avec succes (Role: {new_role}).{C_END}")
                logging.info(f"[{current_admin}] Creation du compte : {new_user} (Role: {new_role})")
            except Exception as e:
                print(f"\n{C_DANGER}Erreur de synchronisation base de donnees : {e}{C_END}")
            time.sleep(2)

        elif choice == '2':
            clear_screen()
            print(f"{C_DANGER}*** SUPPRIMER UN UTILISATEUR ***{C_END}\n")
            
            del_user = input("Nom de l'utilisateur a supprimer (ou '0' pour annuler) : ").strip().lower()
            if del_user == '0':
                print(f"\n{C_WARN}Action annulee.{C_END}")
                time.sleep(1)
                continue
            if del_user == current_admin:
                print(f"{C_DANGER}Impossible de supprimer votre propre compte !{C_END}")
                time.sleep(2)
                continue
            elif del_user not in users:
                print(f"{C_WARN}Utilisateur introuvable.{C_END}")
                time.sleep(1.5)
                continue
            
            print(f"\n{C_WARN}Pour valider la suppression de '{del_user}', veuillez vous authentifier.{C_END}")
            admin_pwd = getpass.getpass(f"Mot de passe de {current_admin} (ou '0' annuler) : ").strip()
            if admin_pwd == '0':
                print(f"\n{C_WARN}Action annulee.{C_END}")
                time.sleep(1)
                continue

            admin_hash = hashlib.sha256(admin_pwd.encode('utf-8')).hexdigest()

            if admin_hash != users[current_admin].get("password"):
                print(f"{C_DANGER}[!] Mot de passe incorrect. Suppression annulee.{C_END}")
                time.sleep(2)
                continue

            try:
                # Verrouillage avant suppression definitive
                with DBLock(USER_DATA_PATH):
                    with open(USER_DATA_PATH, 'r') as f:
                        fresh_users = json.load(f)
                    
                    if del_user in fresh_users:
                        del fresh_users[del_user]
                        with open(USER_DATA_PATH, 'w') as f:
                            json.dump(fresh_users, f, indent=4)
                        print(f"{C_OK}[-] Utilisateur '{del_user}' supprime avec succes.{C_END}")
                        logging.info(f"[{current_admin}] Suppression du compte : {del_user}")
                    else:
                        print(f"{C_WARN}Utilisateur deja supprime par un autre processus.{C_END}")
            except Exception as e:
                print(f"{C_DANGER}Erreur de synchronisation JSON : {e}{C_END}")
            time.sleep(2)

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
                time.sleep(1)
                
        elif c == '2':
            if current_role != "admin":
                continue

            clear_screen()
            print(f"{C_DANGER}=== DESACTIVATION EN COURS ==={C_END}\n")
            logging.warning(f"[{current_user}] Lancement d'un HARD CRASH sur : {', '.join(targets)}")
            
            states = {m: f"{C_BASE}En attente...{C_END}" for m in targets}
            for _ in targets: print()
                
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
            logging.info(f"[{current_user}] Lancement d'un DEMARRAGE sur : {', '.join(targets)}")
            
            states = {m: f"{C_BASE}En attente...{C_END}" for m in targets}
            for _ in targets: print()
                
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
                print(f"{C_WARN}[!] Info : Les machines suivantes sont eteintes et seront ignorees : {', '.join(offline_machines)}{C_END}")
            
            if not online_machines:
                print(f"\n{C_DANGER}[!] Erreur : Aucune machine cible n'est allumee. Action annulee.{C_END}")
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
            map_a = {
                "1":"open_chrome", "2":"close_chrome", 
                "3":"virus_on", "4":"ransomware", "5":"ddos", 
                "6":"virus_off", "7":"ddos_off", "8":"clean"
            }
            act = map_a.get(sub)
            if act:
                logging.warning(f"[{current_user}] Deploiement de l'action '{act}' sur : {', '.join(online_machines)}")
                for m in online_machines:
                    run(f"docker exec {m} python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:5000/trigger?action={act}')\"")
                print(f"{C_OK}[OK] Ordre execute par {current_user}.{C_END}")
                time.sleep(1)
            break
            
        elif c == '0': break

def main():
    while True:
        current_user, current_role = authenticate()
        
        if not current_user:
            sys.exit(1)
            
        print(f"{C_OK}[*] Authentification validee. Bienvenue {current_user} ! (Role: {current_role}){C_END}")
        time.sleep(1)
            
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
                logging.info(f"Fermeture de la session pour : {current_user}")
                print(f"\n{C_OK}Fermeture de la Master Console. Au revoir {current_user} !{C_END}")
                sys.exit(0)
            
            if choice == 'd':
                logging.info(f"Deconnexion manuelle de : {current_user}")
                print(f"\n{C_WARN}Deconnexion de l'utilisateur {current_user} en cours...{C_END}")
                time.sleep(1)
                break 
                
            if choice == 'u' and current_role == 'admin':
                manage_users(current_user)
                continue

            if choice == 'l':
                if current_role == "user":
                    logging.warning(f"[{current_user}] Tentative refusee d'afficher les logs en direct.")
                    print(f"\n{C_DANGER}[!] Commande non reconnue ou acces refuse.{C_END}")
                    time.sleep(1)
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
                    except: continue
                
                if not selected_logs:
                    continue

                online_logs = [m for m in selected_logs if is_container_running(m)]
                offline_logs = [m for m in selected_logs if not is_container_running(m)]

                if not online_logs:
                    print(f"{C_DANGER}[!] Erreur : Aucune machine selectionnee n'est allumee. Lecture des logs impossible.{C_END}")
                    time.sleep(2)
                    continue

                logging.info(f"[{current_user}] Lance la lecture des logs en direct pour : {', '.join(online_logs)}")

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
                                line = q.get_nowait()
                                refresh_screen(line)
                            time.sleep(0.05)
                    except KeyboardInterrupt: pass
                else:
                    import select
                    try:
                        while True:
                            while not q.empty():
                                line = q.get_nowait()
                                refresh_screen(line)
                            if sys.stdin in select.select([sys.stdin], [], [], 0.05)[0]:
                                if sys.stdin.read(1).lower() == 'q':
                                    break
                    except KeyboardInterrupt: pass
                
                for p in procs:
                    try: p.terminate()
                    except: pass
                
                logging.info(f"[{current_user}] Quitte la lecture des logs en direct.")
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
                except: continue
            
            if selected: menu_actions(selected, current_user, current_role)

if __name__ == "__main__":
    try: 
        main()
    except KeyboardInterrupt: 
        logging.warning("Console arretee brutalement par interruption (CTRL+C).")
        print(f"\n\n{C_OK}Master Console arretee brutalement. Au revoir !{C_END}")
        sys.exit(0)