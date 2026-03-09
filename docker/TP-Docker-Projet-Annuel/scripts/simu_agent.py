import time
import os
import random
import sys

machine = os.environ.get('MACHINE_NAME', 'Inconnu')
os_type = os.environ.get('OS_TYPE', 'Inconnu')

print(f"[{machine}] ({os_type}) Démarrage de l'agent...", flush=True)
time.sleep(random.uniform(1.0, 3.0)) 

# Valeurs actuelles au démarrage
cpu_usage = 10.0
gpu_usage = 5.0
ram_usage = 30.0
disk_usage = 15.0
temp_c = 30.0

# Valeurs de "repos" (là où le système tend à retourner naturellement)
base_cpu = 10.0
base_ram = 30.0
base_disk = 15.0

while True:
    # 1. PICS ALÉATOIRES (Les "feintes" instantanées)
    if random.randint(1, 50) == 1:
        cpu_usage = random.uniform(85.0, 100.0)
        gpu_usage = random.uniform(70.0, 100.0)
        print(f"[{machine}] ⚡ Activité : Pic CPU/GPU détecté...", flush=True)
        
    if random.randint(1, 70) == 1:
        ram_usage = random.uniform(85.0, 100.0)
        print(f"[{machine}] 💾 Activité : Allocation massive de RAM...", flush=True)
        
    if random.randint(1, 70) == 1:
        disk_usage = random.uniform(85.0, 100.0)
        print(f"[{machine}] 💽 Activité : Pic d'écriture Disque...", flush=True)

    # 2. LÉGÈRES FLUCTUATIONS DU REPOS
    base_cpu = max(5.0, min(25.0, base_cpu + random.uniform(-2, 2)))
    base_ram = max(20.0, min(45.0, base_ram + random.uniform(-1, 1)))
    base_disk = max(5.0, min(30.0, base_disk + random.uniform(-2, 2)))

    # 3. DESCENTE PROGRESSIVE (L'inertie des ressources)
    # Les multiplicateurs (0.20, 0.10) définissent la vitesse de la baisse.
    cpu_usage += (base_cpu - cpu_usage) * 0.20 
    gpu_usage += (5.0 - gpu_usage) * 0.20
    ram_usage += (base_ram - ram_usage) * 0.10   # La RAM met plus de temps à se purger
    disk_usage += (base_disk - disk_usage) * 0.30 # Le cache disque se vide plus vite

    # 4. CONSÉQUENCE THERMIQUE DIRECTE
    target_temp = 25.0 + (cpu_usage * 0.95) + (gpu_usage * 0.3)
    temp_c += (target_temp - temp_c) * 0.35 + random.uniform(-0.5, 0.5)
    temp_c = max(20.0, min(150.0, temp_c))

    print(f"[{machine}] CPU:{cpu_usage:02.0f}% | RAM:{ram_usage:02.0f}% | Disque:{disk_usage:02.0f}% | Temp:{temp_c:.1f}°C", flush=True)

    # Protocole de sécurité absolu
    if (temp_c + 273.15) > 2500:
        print(f"[{machine}] ALERTE : Il faut toujours garder les systèmes de refroidissement actifs une fois que le cœur dépasse 2500K.", flush=True)
        sys.exit(1)

    time.sleep(2)