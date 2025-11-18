#!/bin/bash
db_path="/home/katiana/monitoring.db"
backup_dir="/home/katiana/sauv_db"
date=$(date +'%y-%m-%d')
backup_file="$backup_dir/sauv_db_file_$date.sqlite"

sqlite3 $db_path ".backup '$backup_file'"
echo "sauvegarde realisée : $backup_file" 
