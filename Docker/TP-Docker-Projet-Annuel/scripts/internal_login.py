import getpass
import hashlib
import os
import sys
import time

# *** DESIGN ***
C_OK = '\033[92m'
C_DANGER = '\033[91m'
C_WARN = '\033[93m'
C_END = '\033[0m'

# *** COMPTES HACHES (SHA-256) ***
ACCOUNTS = {
    "Test": "2c00032e034b28854ef7e34dd050717911dd3a755883e4c4e08bb4001374a979",
    "Arnaud": "fdc65425ed191e98c8a7eacf7542646ebe95d00ac7651ea798701ee50748cfe2",
    "Katiana": "fdc65425ed191e98c8a7eacf7542646ebe95d00ac7651ea798701ee50748cfe2"
}

def start_internal_login():
    os.system('clear')
    print(f"{C_WARN}**********************************************")
    print(f"* CYBER MONITOR : INTERNAL ACCESS      *")
    print(f"**********************************************{C_END}\n")

    for attempt in range(3, 0, -1):
        user = input("Username : ").strip()
        pwd = getpass.getpass("Password : ")
        print()

        hashed_input = hashlib.sha256(pwd.encode('utf-8')).hexdigest()

        if user in ACCOUNTS and ACCOUNTS[user] == hashed_input:
            print(f"{C_OK}[+] Authentification reussie. Connexion en cours...{C_END}")
            time.sleep(1)
            
            os_type = os.environ.get('OS_TYPE', 'Linux')
            shell_path = "/usr/bin/pwsh" if os_type == "Windows" else "/bin/bash"
            
            try:
                os.execlp("su", "su", "-", user, "-s", shell_path)
            except Exception as e:
                print(f"{C_DANGER}[!] Erreur de lancement du shell : {e}{C_END}")
                sys.exit(1)
        else:
            if attempt > 1:
                print(f"{C_DANGER}[!] Identifiants invalides. Il vous reste {attempt - 1} essai(s).{C_END}\n")
            else:
                print(f"{C_DANGER}[!] ECHEC : Verrouillage de la session.{C_END}")
                time.sleep(2)
                sys.exit(1)

if __name__ == "__main__":
    start_internal_login()