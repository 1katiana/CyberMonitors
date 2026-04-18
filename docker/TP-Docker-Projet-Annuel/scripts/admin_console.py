import os
import subprocess
import time
import sys
import threading
import queue

# --- DESIGN ---
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

def capture_logs(pipe, q):
    try:
        for line in iter(pipe.readline, ''):
            if line: q.put(line)
    except: pass
    finally:
        try: pipe.close()
        except: pass

def menu_actions(targets):
    while True:
        if not is_docker_alive(): return
        clear_screen()
        print(f"{C_BASE}=== CIBLES : {', '.join(targets)} ==={C_END}\n")
        print(f"1. {C_OK}Console SSH (1ere cible){C_END}")
        print(f"2. {C_DANGER}Hard Crash (Stop){C_END}")
        print(f"3. {C_OK}Power On (Start){C_END}")
        print(f"4. {C_BASE}Logiciels & Attaques{C_END}")
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
            print(f"\n{C_DANGER}--- ATTAQUES ---{C_END}")
            print("1. Ouvrir Chrome  2. Fermer Chrome  3. Mineur Crypto")
            print("4. Ransomware     5. DDoS           6. Antivirus (10s)")
            print("7. Nettoyage      0. Annuler")
            sub = input("\nAction : ").strip()
            map_a = {"1":"open_chrome","2":"close_chrome","3":"virus_on","4":"ransomware","5":"ddos","6":"virus_off","7":"clean"}
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
        clear_screen()
        if not is_docker_alive():
            print(f"{C_DANGER}ERREUR : DOCKER OFFLINE{C_END}"); time.sleep(3); continue

        m_list = get_machines()
        print(f"{C_BASE}=========================================={C_END}")
        print(f"{C_BASE}       CYBER MONITOR - MASTER CONSOLE     {C_END}")
        print(f"{C_BASE}=========================================={C_END}\n")
        
        for i, m in enumerate(m_list):
            col = C_OK if "Up" in m['status'] else C_DANGER
            print(f"{i+1}. {m['name']} {col}[{m['status']}]{C_END}")
        
        print(f"\n{C_BASE}Entrez des numeros (ex: 1,2), 'toutes', 'L' (Logs) ou 'Q' (Quitter){C_END}")
        choice = input(f"\n{C_WARN}Selection : {C_END}").lower().strip()
        
        if choice == 'q': break
        if choice == 'l':
            clear_screen()
            print(f"{C_BASE}=== LOGS EN DIRECT (Q pour quitter) ==={C_END}\n")
            if os.name == 'nt':
                import msvcrt
                proc = subprocess.Popen(["docker", "compose", "logs", "-f", "--tail=30"], 
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                q = queue.Queue()
                threading.Thread(target=capture_logs, args=(proc.stdout, q), daemon=True).start()
                msg = f"\n{C_WARN}>>> [Q] RETOUR MENU <<<{C_END}"
                try:
                    while True:
                        if msvcrt.kbhit() and msvcrt.getch().lower() == b'q': proc.terminate(); break
                        while not q.empty():
                            line = q.get_nowait()
                            sys.stdout.write("\r" + " " * 90 + "\r" + line)
                            sys.stdout.flush()
                        time.sleep(0.05)
                except: proc.terminate()
            continue

        # --- SELECTION MULTIPLE ---
        selected = []
        if choice in ['toutes', 'all', '*']:
            selected = [m['name'] for m in m_list]
        else:
            try:
                # Gère "1 2", "1,2", "1"
                raw = choice.replace(' ', ',')
                indexes = [int(x) - 1 for x in raw.split(',') if x.isdigit()]
                selected = [m_list[i]['name'] for i in indexes if 0 <= i < len(m_list)]
            except: continue
        
        if selected: menu_actions(selected)

if __name__ == "__main__":
    try: 
        main()
    except KeyboardInterrupt: 
        print(f"\n\n{C_OK}Master Console deconnectee. Au revoir Master ! 👋{C_END}")
        sys.exit(0)