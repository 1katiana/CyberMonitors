import getpass
import hashlib
import os
import sys
import time
import pwd
import json
import subprocess

# *** DESIGN ***
C_OK = '\033[92m'
C_DANGER = '\033[91m'
C_WARN = '\033[93m'
C_BASE = '\033[96m'
C_END = '\033[0m'

def start_internal_login():
    os.system('clear')
    print(f"{C_WARN}**********************************************")
    print(f"* CYBER MONITOR : SECURE ACCESS CONTROL      *")
    print(f"**********************************************{C_END}\n")

    json_path = "/app/Data/Users/users_docker.json"

    for attempt in range(3, 0, -1):
        user = input("Identifiant : ").strip()
        pwd_input = getpass.getpass("Mot de passe : ").strip()
        print()
        
        # *** GESTION DES ERREURS SERIE 100 : FICHIER JSON ***
        try:
            with open(json_path, 'r') as f:
                accounts = json.load(f)
        except FileNotFoundError:
            print(f"{C_DANGER}[!] ERREUR 101 : Le fichier users_docker.json est introuvable.{C_END}")
            print(f"Chemin cherche : {json_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"{C_DANGER}[!] ERREUR 102 : Fichier JSON corrompu (Erreur de syntaxe).{C_END}")
            print(f"Details techniques : {e}")
            sys.exit(1)
        except Exception as e:
            print(f"{C_DANGER}[!] ERREUR 100 : Erreur inconnue lors de la lecture de la base.{C_END}")
            print(f"Details : {e}")
            sys.exit(1)

        hashed = hashlib.sha256(pwd_input.encode('utf-8')).hexdigest()

        # *** GESTION DES ERREURS SERIE 200 : AUTHENTIFICATION ***
        if user not in accounts:
            print(f"{C_DANGER}[!] ERREUR 201 : Utilisateur '{user}' introuvable dans la base.{C_END}")
            if attempt > 1:
                print(f"{C_WARN}Il vous reste {attempt - 1} essai(s).{C_END}\n")
                continue
            else:
                print(f"{C_DANGER}[!] ECHEC : Verrouillage.{C_END}")
                time.sleep(2)
                sys.exit(1)

        if accounts[user].get("password") != hashed:
            print(f"{C_DANGER}[!] ERREUR 202 : Mot de passe incorrect pour '{user}'.{C_END}")
            if attempt > 1:
                print(f"{C_WARN}Il vous reste {attempt - 1} essai(s).{C_END}\n")
                continue
            else:
                print(f"{C_DANGER}[!] ECHEC : Verrouillage.{C_END}")
                time.sleep(2)
                sys.exit(1)

        # Si on passe les erreurs, c'est un succes !
        print(f"{C_OK}[+] Authentification reussie.{C_END}")
        time.sleep(1)
        
        role = accounts[user].get("role", "user")
        
        os_type = os.environ.get('OS_TYPE', 'Linux')
        shell_path = "/usr/bin/pwsh" if os_type == "Windows" else "/bin/bash.real"
        
        # *** GESTION DES ERREURS SERIE 300 : SYSTEME LINUX ***
        try:
            user_info = pwd.getpwnam(user)
            print(f"{C_BASE}[*] Espace local detecte. Chargement du profil '{user}'...{C_END}")
            time.sleep(0.5)
        except KeyError:
            print(f"{C_WARN}[*] Profil local inexistant. Creation de l'espace dedie en cours...{C_END}")
            time.sleep(1.5)
            try:
                subprocess.run(["useradd", "-m", "-s", shell_path, user], check=True, capture_output=True, text=True)
                print(f"{C_OK}[+] Espace '{user}' cree avec succes sur le disque.{C_END}")
                user_info = pwd.getpwnam(user)
            except subprocess.CalledProcessError as e:
                print(f"{C_DANGER}[!] ERREUR 301 : Echec de la commande 'useradd'.{C_END}")
                print(f"Details : {e.stderr.strip()}")
                sys.exit(1)
            except Exception as e:
                print(f"{C_DANGER}[!] ERREUR 302 : Panne systeme inattendue lors de la creation.{C_END}")
                print(f"Details : {e}")
                sys.exit(1)
            time.sleep(1)

        print(f"{C_BASE}[*] Initialisation de la session...{C_END}")
        time.sleep(0.5)

        env = os.environ.copy()
        env['INTERNAL_LOGGED_IN'] = "1" 

        if role == "admin":
            print(f"{C_WARN}[!] Elevation des privileges : Acces Administrateur (ROOT) accorde.{C_END}")
            time.sleep(1)
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

        # *** GESTION DES ERREURS SERIE 400 : SHELL ***
        try:
            os.execlpe(shell_path, shell_path, env)
        except Exception as e:
            print(f"{C_DANGER}[!] ERREUR 401 : Impossible de lancer le terminal virtuel.{C_END}")
            print(f"Details : {e}")
            sys.exit(1)

if __name__ == "__main__":
    start_internal_login()