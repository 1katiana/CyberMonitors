#!/bin/bash

#Récuperer l'utilisation de CPU
cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print 100 - $8"%"}')


#affichage
echo "$cpu_usage"

