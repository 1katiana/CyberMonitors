#!/bin/bash


#execution des script
#bash
cpu_data=$(bash "sonde_cpu.sh")
ram_data=$(bash "sonde_ram.sh")
disk_data=$(bash "sonde_disk.sh")

#python
process_data=$(python3 "sonde_process.py")
users_data=$(python3 "sonde_utilisateurs.py")

#inserer les valeurs dans la bd
sqlite3 monitoring.db "insert into system_data (cpu_usage, ram_usage , disk_usage ,process_count, users_count) values ('$cpu_data','$ram_data','$disk_data','$process_data','$users_data');"

sqlite3 monitoring.db "delete from system_data where id not in (select id from system_data order by timestamp desc limit 10);"


