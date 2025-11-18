#!/bin/bash
db_path="/home/katiana/monitoring.db"
backup_dir="/home/katiana/sauv_db"

echo "liste des sauvgardes disponibles :"
ls -1 "$backup_dir"  | grep 'sauv_db_file_'

echo "entrez le nom du fichier de sauvgardes a restaurer : "
read backup_file

full_backup_path="$backup_dir/$backup_file"

 if [ -f "$full_backup_path" ]; then
      cp "$full_backup_path" "$db_path"


        echo "base de données restaurée avec succés depuis : $full_backup_path"

 else
   echo "erreur : le fichier de sauvgarde n'existe pas !"
 fi

