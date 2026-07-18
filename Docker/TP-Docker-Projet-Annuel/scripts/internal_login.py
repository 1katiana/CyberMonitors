import getpass
import bcrypt
import os
import sys
import time
import pwd
import json
import subprocess
import string
import shutil

# *** DESIGN ***
C_OK = '\033[92m'
C_DANGER = '\033[91m'
C_WARN = '\033[93m'
C_BASE = '\033[96m'
C_END = '\033[0m'

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

def check_password_complexity(pwd):
    missing = []
    if len(pwd) < 12: missing.append("12 caractères minimum") #
    if not any(c.isupper() for c in pwd): missing.append("une majuscule")
    if not any(c.islower() for c in pwd): missing.append("une minuscule")
    if not any(c.isdigit() for c in pwd): missing.append("un chiffre")
    if not any(c in string.punctuation for c in pwd): missing.append("un symbole specifique (!@#$%^&*...)")
    return missing

def start_internal_login():
    os.system('clear')
    print(f"{C_WARN}**********************************************")
    print(f"* CYBER MONITOR : SECURE ACCESS CONTROL      *")
    print(f"**********************************************{C_END}\n")

    json_path = "/app/Data/Users/users_docker.json"

    for attempt in range(3, 0, -1):
        user = input("Identifiant : ").strip().lower()
        pwd_input = getpass.getpass("Mot de passe : ").strip()
        print()
        
        try:
            with DBLock(json_path):
                with open(json_path, 'r') as f:
                    accounts = json.load(f)
        except FileNotFoundError:
            print(f"{C_DANGER}[!] ERREUR 101 : Le fichier users_docker.json est introuvable.{C_END}")
            print(f"Chemin cherche : {json_path}")
            time.sleep(3)
            sys.exit(1)
        except Exception as e:
            print(f"{C_DANGER}[!] ERREUR 100 : Erreur de lecture de la base.{C_END}")
            print(f"Details : {e}")
            time.sleep(3)
            sys.exit(1)

        # Verification Bcrypt securisee
        stored_hash_str = accounts.get(user, {}).get("password", "")
        stored_hash = stored_hash_str.encode('utf-8')
        
        try:
            password_match = bcrypt.checkpw(pwd_input.encode('utf-8'), stored_hash)
        except ValueError:
            password_match = False # Securite si le hash n'est pas au format bcrypt

        if user not in accounts or not password_match:
            if user in accounts and accounts[user].get("reset_by_admin"):
                print(f"{C_DANGER}[!] ACCES REFUSE : Votre mot de passe a ete reinitialise.{C_END}")
                print(f"{C_WARN}Veuillez contacter l'administrateur ou le support IT pour obtenir votre mot de passe temporaire.{C_END}")
                time.sleep(3)
            else:
                print(f"{C_DANGER}[!] ERREUR 200 : Identifiants incorrects.{C_END}")
                time.sleep(2)

            if attempt > 1:
                print(f"{C_WARN}Il vous reste {attempt - 1} essai(s).{C_END}\n")
                continue
            else:
                print(f"{C_DANGER}[!] ECHEC : Verrouillage du terminal.{C_END}")
                time.sleep(2)
                sys.exit(1)

        if accounts[user].get("blocked", False):
            print(f"{C_DANGER}[!] ERREUR 403 : ACCES REFUSE.{C_END}")
            print(f"{C_WARN}Ce compte a ete suspendu par un administrateur.{C_END}")
            time.sleep(3)
            sys.exit(1)

        if accounts[user].get("force_reset"):
            print(f"{C_WARN}[!] PREMIERE CONNEXION OU MISE A JOUR DE SECURITE.{C_END}")
            print(f"Vous devez obligatoirement modifier votre mot de passe.\n")
            time.sleep(2)
            
            while True:
                new_pwd = getpass.getpass("Nouveau mot de passe : ").strip()
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
                except ValueError:
                    pass 

                new_hashed = bcrypt.hashpw(new_pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                break

            try:
                with DBLock(json_path):
                    with open(json_path, 'r') as f: fresh_accounts = json.load(f)
                    fresh_accounts[user]["password"] = new_hashed
                    fresh_accounts[user]["force_reset"] = False
                    fresh_accounts[user]["reset_by_admin"] = False
                    with open(json_path, 'w') as f: json.dump(fresh_accounts, f, indent=4)
                print(f"{C_OK}[+] Mot de passe mis a jour avec succes.{C_END}")
                time.sleep(2)
            except Exception as e:
                print(f"{C_DANGER}Erreur BDD lors de la sauvegarde : {e}{C_END}")
                time.sleep(3)
                sys.exit(1)

        print(f"{C_OK}[+] Authentification reussie.{C_END}")
        time.sleep(1)
        
        role = accounts[user].get("role", "user")
        
        os_type = os.environ.get('OS_TYPE', 'Linux')
        shell_path = "/bin/bash.real" # Shell de secours par defaut
        
        if os_type == "Windows":
            pwsh_loc = shutil.which("pwsh")
            if pwsh_loc and os.path.exists(pwsh_loc):
                shell_path = pwsh_loc
            elif os.path.exists("/opt/microsoft/powershell/7/pwsh"):
                shell_path = "/opt/microsoft/powershell/7/pwsh"
            elif os.path.exists("/usr/bin/pwsh"):
                shell_path = "/usr/bin/pwsh"
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

        try:
            os.execlpe(shell_path, shell_path, env)
        except Exception as e:
            print(f"{C_DANGER}[!] ERREUR 401 : Impossible de lancer le terminal virtuel.{C_END}")
            print(f"Details : {e}")
            time.sleep(3)
            sys.exit(1)

if __name__ == "__main__":
    start_internal_login()