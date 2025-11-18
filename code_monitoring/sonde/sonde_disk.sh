#!/bin/bash

#recuperer l'utilisation du disque
disk_usage=$(df -h | grep ' /$' | awk '{print $5}')

echo "$disk_usage"


