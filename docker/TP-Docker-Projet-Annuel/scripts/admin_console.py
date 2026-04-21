import os
import subprocess
import time
import sys
import threading
import queue
import getpass
import hashlib

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
    valid_users_hashes = {
        "Test": hashlib.sha256(b"Test!").hexdigest(),
        "Arnaud": hashlib.sha256(b"CyberMonitor2026!").hexdigest(),
        "Katiana": hashlib.sha256(b"CyberMonitor2026!").hexdigest()
    }

    for attempt in range(3, 0, -1):
        clear_screen()
        print(f"{C_WARN}*** ACCES RESTREINT : AUTHENTIFICATION REQUISE ***{C_END}")
        print(f"Connexion a la Master Console.\n")
        
        user = input("Identifiant : ").strip()
        pwd = getpass.getpass("Mot de passe : ")
        
        print()
        
        hashed_pwd = hashlib.sha256(pwd.encode('utf-8')).hexdigest()

        if user in valid_users_hashes and valid_users_hashes[user] == hashed_pwd:
            print(f"{C_OK}[*] Acces autorise. Bienvenue {user}.{C_END}")
            time.sleep(1)
            return True
        else:
            if attempt > 1:
                print(f"{C_DANGER}Identifiants incorrects. Il vous reste {attempt - 1} essai(s).{C_END}")
                time.sleep(2)
            else:
                print(f"{C_DANGER}[!] ACCES REFUSE. Incident de securite enregistre.{C_END}")
                time.sleep(2)
                return False

def capture_container_logs(container, q_out, proc_list):
    proc = subprocess.Popen(["docker", "logs", "-f", "--tail=20", container], 
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    proc_list.append(proc)
    try:
        for line in iter(proc.stdout.readline, ''):
            if line: q_out.put(f"{C_BASE}[{container}]{C_END} {line.strip()}")
    except: pass

def menu_actions(targets):
    while True:
        if not is_docker_alive(): return
        clear_screen()
        print(f"{C_BASE}=== CIBLES : {', '.join(targets)} ==={C_END}\n")
        print(f"1. {C_OK}Console SSH (1ere cible){C_END}")
        print(f"2. {C_DANGER}Hard Crash (Stop){C_END}")
        print(f"3. {C_OK}Power On (Start){C_END}")
        print(f"4. {C_BASE}Logiciels et Attaques{C_END}")
        print("0. Retour")
        
        c = input(f"\nChoix : ").strip()
        
        if c == '1':
            m = targets[0]
            if is_container_running(m):
                sh = "pwsh" if "win" in m.lower() else "bash"
                os.system(f"docker exec -it {m} {sh} || docker exec -it {m} /bin/sh")
            else:
                print(f"{C_WARN}[!] Machine eteinte.{C_END}"); time.sleep(1)
        elif c == '2':
            for m in targets:
                print(f"{C_WARN}[...] Arret de {m}{C_END}")
                run(f"docker stop {m}")
            print(f"{C_DANGER}[OK] Cibles stoppees.{C_END}"); time.sleep(1); break
        elif c == '3':
            for m in targets:
                print(f"{C_WARN}[...] Demarrage de {m}{C_END}")
                run(f"docker start {m}")
            print(f"{C_OK}[OK] Cibles en ligne.{C_END}"); time.sleep(1); break
        elif c == '4':
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
                for m in targets:
                    if is_container_running(m):
                        run(f"docker exec {m} python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:5000/trigger?action={act}')\"")
                print(f"{C_OK}[OK] Action envoyee.{C_END}"); time.sleep(1)
            break
        elif c == '0': break

def main():
    while True:
        if not authenticate():
            sys.exit(1)
            
        while True:
            clear_screen()
            if not is_docker_alive():
                print(f"{C_DANGER}ERREUR : DOCKER OFFLINE{C_END}"); time.sleep(3); continue

            m_list = get_machines()
            print(f"{C_BASE}=========================================={C_END}")
            print(f"{C_BASE}       CYBER MONITOR : MASTER CONSOLE     {C_END}")
            print(f"{C_BASE}=========================================={C_END}\n")
            
            for i, m in enumerate(m_list):
                col = C_OK if "Up" in m['status'] else C_DANGER
                print(f"{i+1}. {m['name']} {col}[{m['status']}]{C_END}")
            
            print(f"\n{C_BASE}Commandes : Numeros (ex: 1,2), 'toutes', 'L' (Logs), 'D' (Deconnexion), 'Q' (Quitter){C_END}")
            choice = input(f"\n{C_WARN}Selection : {C_END}").lower().strip()
            
            if choice == 'q':
                print(f"\n{C_OK}Fermeture de la Master Console. Au revoir!{C_END}")
                sys.exit(0)
            
            if choice == 'd':
                print(f"\n{C_OK}Deconnexion en cours...{C_END}")
                time.sleep(1)
                break 
                
            if choice == 'l':
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

                clear_screen()
                print(f"{C_BASE}=== LOGS EN DIRECT : {', '.join(selected_logs)} ==={C_END}\n")
                
                q = queue.Queue()
                procs = []
                
                for m_name in selected_logs:
                    threading.Thread(target=capture_container_logs, args=(m_name, q, procs), daemon=True).start()

                msg = f"{C_WARN}>>> [Q] RETOUR MENU <<<{C_END}"
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
                                sys.stdout.write("\r" + " " * 80 + "\r" + line + "\n" + msg)
                                sys.stdout.flush()
                            time.sleep(0.05)
                    except KeyboardInterrupt: pass
                else:
                    import select
                    try:
                        while True:
                            while not q.empty():
                                line = q.get_nowait()
                                sys.stdout.write("\r" + " " * 80 + "\r" + line + "\n" + msg)
                                sys.stdout.flush()
                            if sys.stdin in select.select([sys.stdin], [], [], 0.05)[0]:
                                if sys.stdin.read(1).lower() == 'q':
                                    break
                    except KeyboardInterrupt: pass
                
                for p in procs:
                    try: p.terminate()
                    except: pass
                
                sys.stdout.write("\r" + " " * 80 + "\r")
                sys.stdout.flush()
                continue

            # *** SELECTION MULTIPLE ***
            selected = []
            if choice in ['toutes', 'all', '*']:
                selected = [m['name'] for m in m_list]
            else:
                try:
                    raw = choice.replace(' ', ',')
                    indexes = [int(x) - 1 for x in raw.split(',') if x.isdigit()]
                    selected = [m_list[i]['name'] for i in indexes if 0 <= i < len(m_list)]
                except: continue
            
            if selected: menu_actions(selected)

if __name__ == "__main__":
    try: 
        main()
    except KeyboardInterrupt: 
        print(f"\n\n{C_OK}Master Console arretee. Au revoir!{C_END}")
        sys.exit(0)