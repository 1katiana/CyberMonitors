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
import logging # Module de journalisation

# *** CONFIGURATION DES LOGS ***
current_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.normpath(os.path.join(current_dir, "..", "..", "..", "Data", "Logs"))
os.makedirs(log_dir, exist_ok=True) # S'assure que le dossier existe
log_file = os.path.join(log_dir, "Logs_Console_Admin.log")

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# *** DESIGN ***
C_BASE = '\033[96m'
C_OK = '\033[92m'
C_WARN = '\033[93m'
C_DANGER = '\033[91m'
C_END = '\033[0m'

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

def authenticate():
    user_data_path = os.path.normpath(os.path.join(current_dir, "..", "..", "..", "Data", "Users", "users_docker.json"))

    for attempt in range(3, 0, -1):
        clear_screen()
        print(f"{C_WARN}*** ACCES RESTREINT : AUTHENTIFICATION REQUISE ***{C_END}")
        print(f"Connexion a la Master Console.\n")
        
        user = input("Identifiant : ").strip()
        pwd = getpass.getpass("Mot de passe : ").strip()
        
        print()
        
        # *** GESTION DES ERREURS SERIE 100 : FICHIER JSON ***
        try:
            with open(user_data_path, 'r') as f:
                valid_users = json.load(f)
        except FileNotFoundError:
            print(f"{C_DANGER}[!] ERREUR 101 : Le fichier users_docker.json est introuvable.{C_END}")
            logging.error(f"ERREUR 101 : Fichier introuvable ({user_data_path})")
            time.sleep(4)
            return None, None
        except json.JSONDecodeError as e:
            print(f"{C_DANGER}[!] ERREUR 102 : Fichier JSON corrompu (Erreur de syntaxe).{C_END}")
            logging.error(f"ERREUR 102 : Syntaxe JSON invalide. Details: {e}")
            time.sleep(4)
            return None, None
        except Exception as e:
            print(f"{C_DANGER}[!] ERREUR 100 : Impossible de lire la base des utilisateurs.{C_END}")
            logging.error(f"ERREUR 100 : Inconnue. Details: {e}")
            time.sleep(4)
            return None, None
        
        hashed_pwd = hashlib.sha256(pwd.encode('utf-8')).hexdigest()

        # *** GESTION DES ERREURS SERIE 200 : AUTHENTIFICATION ***
        if user not in valid_users:
            print(f"{C_DANGER}[!] ERREUR 201 : Utilisateur '{user}' introuvable dans la base.{C_END}")
            logging.warning(f"Tentative ECHOUEE (201) - Compte inexistant: {user}")
            if attempt > 1:
                print(f"{C_WARN}Il vous reste {attempt - 1} essai(s).{C_END}")
                time.sleep(2)
                continue
            else:
                print(f"{C_DANGER}[!] ACCES REFUSE. Incident de securite enregistre.{C_END}")
                logging.error(f"ACCES BLOQUE - Multiples echecs (201) pour : {user}")
                time.sleep(2)
                return None, None

        if valid_users[user].get("password") != hashed_pwd:
            print(f"{C_DANGER}[!] ERREUR 202 : Mot de passe incorrect pour '{user}'.{C_END}")
            logging.warning(f"Tentative ECHOUEE (202) - Mauvais mot de passe pour: {user}")
            if attempt > 1:
                print(f"{C_WARN}Il vous reste {attempt - 1} essai(s).{C_END}")
                time.sleep(2)
                continue
            else:
                print(f"{C_DANGER}[!] ACCES REFUSE. Incident de securite enregistre.{C_END}")
                logging.error(f"ACCES BLOQUE - Multiples echecs (202) pour : {user}")
                time.sleep(2)
                return None, None

        # Si tout est OK
        role = valid_users[user].get("role", "user")
        logging.info(f"Connexion REUSSIE - Utilisateur: {user} | Role: {role}")
        return user, role

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
                logging.warning(f"[{current_user}] Tentative d'acces refuse (Hard Crash)")
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
                logging.warning(f"[{current_user}] Tentative d'acces refuse (Power On)")
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
                logging.warning(f"[{current_user}] Tentative d'acces refuse (Attaques)")
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
            
            if current_role == "user":
                print(f"\n{C_BASE}Commandes : Numeros (ex: 1,2), 'toutes', 'D' (Deconnexion), 'Q' (Quitter){C_END}")
            else:
                print(f"\n{C_BASE}Commandes : Numeros (ex: 1,2), 'toutes', 'L' (Logs), 'D' (Deconnexion), 'Q' (Quitter){C_END}")
                
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