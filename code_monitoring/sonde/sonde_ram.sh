#!/bin/bash

#recuperer l'utilisation de la RAM
ram_usage=$(free -m | awk '/Mem/ {printf "%.2f%%", $3/$2 * 100}')

echo "$ram_usage"
