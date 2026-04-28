import os
import sqlite3
import glob
import shutil
from datetime import datetime, timedelta

# Definition des chemins absolus par rapport a ce script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# On remonte de 'code_monitoring/gestion de sauvegarde' vers la racine
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

DB_PATH = os.path.join(BASE_DIR, "Data", "monitoring.db")
BACKUP_DIR = os.path.join(BASE_DIR, "Data", "backups")

def nettoyer_vieux_backups():
    # Supprime les sauvegardes de plus de 7 jours
    limite = datetime.now() - timedelta(days=7)
    backups = glob.glob(os.path.join(BACKUP_DIR, "*.sqlite"))
    for b in backups:
        mtime = datetime.fromtimestamp(os.path.getmtime(b))
        if mtime < limite:
            os.remove(b)
            print(f"[*] Ancienne sauvegarde supprimee : {os.path.basename(b)}")

def faire_sauvegarde():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y_%m_%d_%Hh%M")
    backup_file = os.path.join(BACKUP_DIR, f"backup_db_{date_str}.sqlite")
    
    try:
        if not os.path.exists(DB_PATH):
            print(f"[ERREUR] La base source est introuvable : {DB_PATH}")
            return

        # Utilisation de l'API native sqlite3 pour une sauvegarde a chaud sans corrompre les donnees
        source = sqlite3.connect(DB_PATH)
        dest = sqlite3.connect(backup_file)
        source.backup(dest)
        source.close()
        dest.close()
        
        print(f"[OK] Sauvegarde reussie : {os.path.basename(backup_file)}")
        nettoyer_vieux_backups()
    except Exception as e:
        print(f"[ERREUR] Echec de la sauvegarde : {e}")

def restaurer_sauvegarde():
    if not os.path.exists(BACKUP_DIR):
        print("[ERREUR] Aucun dossier de sauvegarde trouve.")
        return

    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "*.sqlite")), reverse=True)
    if not backups:
        print("[ERREUR] Aucune sauvegarde disponible.")
        return

    print("\n*** SAUVEGARDES DISPONIBLES ***")
    for i, b in enumerate(backups):
        taille = os.path.getsize(b) / 1024
        nom = os.path.basename(b)
        print(f"{i + 1}. {nom} ({taille:.1f} Ko)")

    choix = input("\nEntrez le numero de la sauvegarde a restaurer (ou 0 pour annuler) : ")
    try:
        choix_idx = int(choix) - 1
        if choix_idx == -1:
            return
        if 0 <= choix_idx < len(backups):
            fichier_choisi = backups[choix_idx]
            print(f"Restauration de {os.path.basename(fichier_choisi)} en cours...")
            
            # Remplacement brutal mais efficace du fichier db
            shutil.copy2(fichier_choisi, DB_PATH)
            
            print("[OK] Base de donnees restauree avec succes !")
            print("[!] Pense a rafraichir le Dashboard web pour voir les donnees restaurees.")
        else:
            print("[ERREUR] Numero invalide.")
    except ValueError:
        print("[ERREUR] Veuillez entrer un numero valide.")

def menu():
    while True:
        print("\n==================================")
        print("    GESTIONNAIRE DE SAUVEGARDES   ")
        print("==================================")
        print("1. Creer un Snapshot (Sauvegarde)")
        print("2. Restaurer une Base de donnees")
        print("0. Quitter")
        
        c = input("\nAction : ").strip()
        if c == '1':
            faire_sauvegarde()
        elif c == '2':
            restaurer_sauvegarde()
        elif c == '0':
            break

if __name__ == "__main__":
    menu()