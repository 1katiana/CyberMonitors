import os
import glob
import shutil
import zipfile
import datetime
import json
import bcrypt
import getpass
import sys
import logging
import time
import subprocess

# *** DESIGN ***
C_BASE = '\033[96m'
C_OK = '\033[92m'
C_WARN = '\033[93m'
C_DANGER = '\033[91m'
C_END = '\033[0m'

# *** CHEMINS ABSOLUS ***
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

DATA_DIR = os.path.join(BASE_DIR, "Data")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
LOG_DIR = os.path.join(DATA_DIR, "Logs")
USERS_DB = os.path.join(DATA_DIR, "Users", "users_docker.json")
DOCKER_DIR = os.path.normpath(os.path.join(BASE_DIR, "docker", "TP-Docker-Projet-Annuel"))

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# *** CONFIGURATION DES LOGS ***
log_file = os.path.join(LOG_DIR, "Backup_Manager.log")
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# *** AUTHENTIFICATION ***
def authenticate():
    clear_screen()
    print(f"{C_WARN}**********************************************")
    print(f"* PRA MONITORING : AUTHENTIFICATION ADMIN    *")
    print(f"**********************************************{C_END}\n")

    if not os.path.exists(USERS_DB):
        print(f"{C_DANGER}[!] Erreur Critique : Base des utilisateurs introuvable.{C_END}")
        sys.exit(1)

    for attempt in range(3, 0, -1):
        user = input("Identifiant : ").strip().lower()
        pwd = getpass.getpass("Mot de passe : ").strip()
        print()

        try:
            with open(USERS_DB, 'r') as f:
                users = json.load(f)
        except Exception as e:
            print(f"{C_DANGER}[!] Erreur de lecture BDD : {e}{C_END}")
            sys.exit(1)

        stored_hash_str = users.get(user, {}).get("password", "")
        stored_hash = stored_hash_str.encode('utf-8')

        try:
            password_match = bcrypt.checkpw(pwd.encode('utf-8'), stored_hash)
        except ValueError:
            password_match = False

        if user in users and password_match:
            role = users[user].get("role", "user")
            if role != "admin":
                print(f"{C_DANGER}[!] ACCES REFUSE : Privileges administrateur requis.{C_END}")
                logging.warning(f"Tentative d'acces aux backups refusee pour l'utilisateur non-admin : {user}")
                time.sleep(2)
                sys.exit(1)
            
            print(f"{C_OK}[+] Authentification reussie. Bienvenue {user}.{C_END}")
            logging.info(f"[{user}] Connexion au gestionnaire de sauvegarde reussie.")
            return user
        else:
            print(f"{C_DANGER}[!] Identifiants incorrects.{C_END}")
            if attempt > 1:
                print(f"{C_WARN}Il reste {attempt - 1} essai(s).{C_END}\n")
            else:
                logging.warning(f"Echecs multiples de connexion au gestionnaire de sauvegarde (Utilisateur tente : {user})")
                time.sleep(2)
                sys.exit(1)

# *** LOGIQUE AUTO-BACKUP (7 JOURS) ***
def check_auto_backup(current_user):
    backups = glob.glob(os.path.join(BACKUP_DIR, "CyberMonitor_Backup_*.zip"))
    needs_backup = True

    if backups:
        newest_backup = max(backups, key=os.path.getctime)
        backup_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getctime(newest_backup))
        if backup_age.days < 7:
            needs_backup = False

    if needs_backup:
        print(f"{C_WARN}[*] Aucune sauvegarde de moins de 7 jours detectee. Lancement automatique...{C_END}")
        logging.info("Declenchement de l'auto-sauvegarde (Delai de 7 jours depasse).")
        create_full_backup("AUTO_SYSTEM")

# *** CREATION DE BACKUP ***
def create_full_backup(initiator):
    date_str = datetime.datetime.now().strftime("%Y_%m_%d_%Hh%M")
    backup_filename = f"CyberMonitor_Backup_{date_str}.zip"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    print(f"\n{C_WARN}[*] Etape 1/3 : Arret des conteneurs pour securiser l'integrite des donnees...{C_END}")
    subprocess.run(["docker", "compose", "stop"], cwd=DOCKER_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print(f"{C_BASE}[*] Etape 2/3 : Preparation de l'archive {backup_filename}...{C_END}")
    
    try:
        files_to_zip = []
        total_size = 0
        
        # Pre-calcul pour la barre de progression
        for root, dirs, files in os.walk(BASE_DIR):
            if 'backups' in dirs: dirs.remove('backups')
            if '.git' in dirs: dirs.remove('.git')
            if '__pycache__' in dirs: dirs.remove('__pycache__')

            for file in files:
                file_path = os.path.join(root, file)
                files_to_zip.append(file_path)
                total_size += os.path.getsize(file_path)

        start_time = time.time()
        processed_size = 0

        # Compression avec progression
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for i, file_path in enumerate(files_to_zip):
                arcname = os.path.relpath(file_path, BASE_DIR)
                zipf.write(file_path, arcname)

                processed_size += os.path.getsize(file_path)
                progress = processed_size / total_size if total_size > 0 else 1
                elapsed = time.time() - start_time
                eta = (elapsed / progress) * (1 - progress) if progress > 0 else 0

                bar_len = 35
                filled = int(bar_len * progress)
                bar = '#' * filled + '-' * (bar_len - filled)
                pct = int(progress * 100)
                
                sys.stdout.write(f"\r{C_BASE}    [{bar}] {pct}% | ETA: {int(eta)}s{C_END}")
                sys.stdout.flush()

        print(f"\n{C_OK}[+] Etape 2/3 : Sauvegarde complete reussie !{C_END}")
        logging.info(f"[{initiator}] Sauvegarde creee avec succes : {backup_filename}")
        
    except Exception as e:
        print(f"\n{C_DANGER}[!] Erreur lors de la sauvegarde : {e}{C_END}")
        logging.error(f"[{initiator}] Echec de la sauvegarde : {e}")
        
    finally:
        print(f"{C_WARN}[*] Etape 3/3 : Redemarrage des conteneurs (docker compose start)...{C_END}")
        subprocess.run(["docker", "compose", "start"], cwd=DOCKER_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"{C_OK}[+] Infrastructure de nouveau en ligne.{C_END}")

# *** RESTAURATION ***
def restore_backup(initiator):
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "CyberMonitor_Backup_*.zip")), reverse=True)
    if not backups:
        print(f"{C_DANGER}[!] Aucune sauvegarde disponible.{C_END}")
        input("\nAppuyez sur Entree pour revenir.")
        return

    print(f"\n{C_BASE}*** SAUVEGARDES DISPONIBLES ***{C_END}")
    for i, b in enumerate(backups):
        size_mb = os.path.getsize(b) / (1024 * 1024)
        print(f"{i + 1}. {os.path.basename(b)} ({size_mb:.1f} Mo)")

    choice = input("\nNumero a restaurer (0 = annuler) : ").strip()
    if choice == '0' or not choice.isdigit():
        return

    idx = int(choice) - 1
    if 0 <= idx < len(backups):
        target = backups[idx]
        print(f"\n{C_WARN}ATTENTION : La restauration ecrasera les fichiers actuels.{C_END}")
        confirm = input("Confirmer la restauration (o/n) : ").strip().lower()
        
        if confirm == 'o':
            print(f"{C_WARN}[*] Arret des conteneurs pour la restauration...{C_END}")
            subprocess.run(["docker", "compose", "stop"], cwd=DOCKER_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            print(f"{C_BASE}[*] Extraction de l'archive en cours...{C_END}")
            try:
                with zipfile.ZipFile(target, 'r') as zipf:
                    zipf.extractall(BASE_DIR)
                print(f"{C_OK}[+] Restauration terminee avec succes.{C_END}")
                logging.warning(f"[{initiator}] A RESTAURE l'infrastructure depuis l'archive : {os.path.basename(target)}")
            except Exception as e:
                print(f"{C_DANGER}[!] Erreur lors de la restauration : {e}{C_END}")
                logging.error(f"[{initiator}] Echec de restauration : {e}")
            finally:
                print(f"{C_WARN}[*] Redemarrage des conteneurs...{C_END}")
                subprocess.run(["docker", "compose", "start"], cwd=DOCKER_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"{C_OK}[+] Infrastructure de nouveau en ligne.{C_END}")
                
    input("\nAppuyez sur Entree pour revenir.")

# *** CHIRURGIE D'ARCHIVE (CONSULTATION / SUPPRESSION) ***
def manage_archives(initiator):
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "CyberMonitor_Backup_*.zip")), reverse=True)
    if not backups:
        print(f"{C_DANGER}[!] Aucune sauvegarde disponible.{C_END}")
        input("\nAppuyez sur Entree pour revenir.")
        return

    print(f"\n{C_BASE}*** GESTION DES ARCHIVES ***{C_END}")
    for i, b in enumerate(backups):
        size_mb = os.path.getsize(b) / (1024 * 1024)
        print(f"{i + 1}. {os.path.basename(b)} ({size_mb:.1f} Mo)")

    choice = input("\nNumero de l'archive a inspecter (0 = annuler) : ").strip()
    if choice == '0' or not choice.isdigit():
        return

    idx = int(choice) - 1
    if 0 <= idx < len(backups):
        target = backups[idx]
        target_name = os.path.basename(target)
        
        while True:
            clear_screen()
            print(f"{C_BASE}=== ARCHIVE : {target_name} ==={C_END}")
            print("1. Lister le contenu (Consultation)")
            print("2. Supprimer un fichier specifique a l'interieur de l'archive")
            print(f"3. {C_DANGER}Supprimer l'archive complete{C_END}")
            print("0. Retour")

            sub_choice = input("\nAction : ").strip()
            
            if sub_choice == '1':
                try:
                    with zipfile.ZipFile(target, 'r') as zipf:
                        files = zipf.namelist()
                        # Filtre intelligent pour la console
                        files_to_show = [f for f in files if not f.endswith('.gitignore') and not f.endswith('.gitkeep')]
                        
                        print(f"\n{C_OK}Contenu complet de l'archive (Masque les .gitignore/.gitkeep) :{C_END}")
                        for f in files_to_show:
                            print(f" - {f}")
                            
                        print(f"\n{C_BASE}Total affiche : {len(files_to_show)} fichiers (Total reel avec configs : {len(files)} fichiers).{C_END}")
                except Exception as e:
                    print(f"{C_DANGER}Impossible de lire l'archive : {e}{C_END}")
                input("\nAppuyez sur Entree pour revenir.")

            elif sub_choice == '2':
                file_to_remove = input("\nChemin exact du fichier a supprimer (ex: Data/Logs/erreur.log) : ").strip()
                if not file_to_remove: continue

                temp_target = target + ".temp"
                file_found = False

                print(f"{C_BASE}[*] Modification de l'archive en cours...{C_END}")
                try:
                    with zipfile.ZipFile(target, 'r') as zin:
                        with zipfile.ZipFile(temp_target, 'w', zipfile.ZIP_DEFLATED) as zout:
                            for item in zin.infolist():
                                if item.filename != file_to_remove:
                                    zout.writestr(item, zin.read(item.filename))
                                else:
                                    file_found = True
                    
                    if file_found:
                        os.replace(temp_target, target)
                        print(f"{C_OK}[+] Fichier '{file_to_remove}' supprime de l'archive.{C_END}")
                        logging.info(f"[{initiator}] A supprime '{file_to_remove}' de l'archive {target_name}")
                    else:
                        os.remove(temp_target)
                        print(f"{C_WARN}[!] Fichier introuvable dans l'archive.{C_END}")
                except Exception as e:
                    if os.path.exists(temp_target): os.remove(temp_target)
                    print(f"{C_DANGER}[!] Erreur de manipulation ZIP : {e}{C_END}")
                input("\nAppuyez sur Entree pour revenir.")

            elif sub_choice == '3':
                confirm = input(f"{C_DANGER}Confirmer la suppression definitive de {target_name} ? (o/n) : {C_END}").strip().lower()
                if confirm == 'o':
                    os.remove(target)
                    print(f"{C_OK}[+] Archive supprimee.{C_END}")
                    logging.info(f"[{initiator}] A detruit l'archive : {target_name}")
                    input("\nAppuyez sur Entree pour revenir.")
                    break

            elif sub_choice == '0':
                break

# *** MENU PRINCIPAL ***
def menu(current_user):
    check_auto_backup(current_user)

    while True:
        clear_screen()
        print(f"{C_BASE}=============================================={C_END}")
        print(f"{C_BASE}    PRA CYBER MONITOR - MASTER BACKUP         {C_END}")
        print(f"{C_WARN}    Operateur : {current_user.upper()}        {C_END}")
        print(f"{C_BASE}=============================================={C_END}\n")
        
        print(f"1. {C_OK}Creer un Snapshot Complet (Infrastructure & Donnees){C_END}")
        print(f"2. {C_DANGER}Restaurer une sauvegarde (Rollback){C_END}")
        print(f"3. {C_WARN}Gere les Archives (Consulter, Modifier, Supprimer){C_END}")
        print(f"4. {C_BASE}Consulter les logs de sauvegarde{C_END}")
        print("\n0. Quitter")
        
        c = input("\nAction : ").strip()
        
        if c == '1':
            create_full_backup(current_user)
            input("\nAppuyez sur Entree pour continuer.")
        elif c == '2':
            restore_backup(current_user)
        elif c == '3':
            manage_archives(current_user)
        elif c == '4':
            clear_screen()
            print(f"{C_BASE}=== LOGS DU GESTIONNAIRE DE SAUVEGARDE ==={C_END}\n")
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-25:]:
                        print(line.strip())
            else:
                print("Aucun log disponible.")
            input("\nAppuyez sur Entree pour revenir.")
        elif c == '0':
            print(f"\n{C_OK}Fermeture du PRA. Au revoir {current_user}.{C_END}")
            break

if __name__ == "__main__":
    try:
        admin_user = authenticate()
        menu(admin_user)
    except KeyboardInterrupt:
        print(f"\n{C_OK}Arret brutal. Au revoir !{C_END}")
        sys.exit(0)