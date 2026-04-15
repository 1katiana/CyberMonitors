import os
import subprocess
import time

# --- PALETTE COULEURS ---
C_BASE = '\033[96m'   # Cyan
C_OK = '\033[92m'     # Vert
C_WARN = '\033[93m'   # Jaune
C_DANGER = '\033[91m' # Rouge
C_END = '\033[0m'

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()

def get_machines():
    out = run('docker ps --format "{{.Names}}|{{.Status}}"')
    machines = []
    if out:
        for line in out.split('\n'):
            if '|' in line:
                name, status = line.split('|', 1)
                if any(x in name.lower() for x in ['srv', 'wkst', 'center']):
                    machines.append({"name": name, "status": status})
    return machines

def menu_actions(targets):
    t_str = ", ".join(targets)
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{C_BASE}=== CIBLES ACTIVES : {t_str} ==={C_END}\n")
        print(f"1. {C_OK}[SYSTEM]  Ouvrir Terminal (1ere cible){C_END}")
        print(f"2. {C_DANGER}[HARDWARE] Crash Materiel (Stop){C_END}")
        print(f"3. {C_OK}[HARDWARE] Redemarrage (Start){C_END}")
        print(f"4. {C_BASE}[SOFTWARE] Menu Attaques et Logiciels{C_END}")
        print("0. Retour")
        
        c = input(f"\nChoix : ")
        if c == '1':
            m = targets[0]
            sh = "pwsh" if "win" in m.lower() else "bash"
            os.system(f"docker exec -it {m} {sh} || docker exec -it {m} /bin/sh")
        elif c == '2':
            for m in targets: run(f"docker stop {m}")
            break
        elif c == '3':
            for m in targets: run(f"docker start {m}")
            break
        elif c == '4':
            print(f"\n{C_DANGER}--- VECTEURS D'ATTAQUE ---{C_END}")
            print(f"1. {C_BASE}Ouvrir Chrome (+RAM){C_END} | 2. {C_WARN}Fermer Chrome{C_END}")
            print(f"3. {C_DANGER}Mineur Crypto (CPU 100%){C_END}")
            print(f"4. {C_DANGER}Ransomware (Disk 100%){C_END}")
            print(f"5. {C_DANGER}Inondation DDoS (Traffic){C_END}")
            print(f"6. {C_OK}Antivirus / Fix Global{C_END}")
            print(f"7. {C_OK}Nettoyage Disque{C_END}")
            
            sub = input("\nAction : ")
            map_a = {"1":"open_chrome", "2":"close_chrome", "3":"virus_on", 
                     "4":"ransomware", "5":"ddos", "6":"virus_off", "7":"clean"}
            act = map_a.get(sub)
            if act:
                for m in targets:
                    # Commande blindee pour Windows/Linux Docker
                    run(f"docker exec {m} python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:5000/trigger?action={act}')\"")
                print(f"\n{C_OK}Signal envoye.{C_END}")
                time.sleep(1)
        elif c == '0': break

def main():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        machines = get_machines()
        print(f"{C_BASE}=========================================={C_END}")
        print(f"{C_BASE}       CYBER MONITOR - MASTER CONSOLE     {C_END}")
        print(f"{C_BASE}=========================================={C_END}\n")
        
        for i, m in enumerate(machines):
            col = C_OK if "Up" in m['status'] else C_DANGER
            print(f"{i+1}. {m['name']} {col}[{m['status']}]{C_END}")
        
        print(f"\n{C_BASE}Entrez des numeros (ex: 1,3), 'toutes' ou 'Q'{C_END}")
        choice = input("Cibles : ").lower()
        
        if choice == 'q': break
        
        selected = []
        if choice in ['toutes', 'all', '*']:
            selected = [m['name'] for m in machines]
        else:
            try:
                ids = [int(x.strip()) - 1 for x in choice.split(',')]
                selected = [machines[i]['name'] for i in ids if 0 <= i < len(machines)]
            except: continue
            
        if selected: menu_actions(selected)

if __name__ == "__main__":
    main()