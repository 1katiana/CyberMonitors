# -*- coding: utf-8 -*-
import sqlite3
import pygal
from pygal.style import DarkStyle  # Import important
import os

DB_PATH = "/app/data/monitoring.db"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "static", "graphs")

def create_chart(title, labels, values, color, filename, is_user_chart=False):
    """Crée un graphique Pygal avec un style sombre."""
    custom_style = DarkStyle(
        background='transparent',
        plot_background='transparent',
        foreground='#ffffff',
        foreground_strong='#ffffff',
        foreground_subtle='#a0a0a0',
        opacity='.6',
        opacity_hover='.9',
        colors=(color,)
    )

    chart = pygal.Line(
        x_label_rotation=20, 
        height=250, 
        show_legend=False, 
        explicit_size_hint=True,
        style=custom_style
    )
    
    # Axe ordonné en nombres entiers pour les utilisateurs
    if is_user_chart:
        max_val = int(max(values)) if values else 5
        
        if max_val < 15:
            # Si peu d'utilisateurs, on affiche 1, 2, 3...
            chart.y_labels = list(range(0, max_val + 2))
        else:
            # Si DDoS ou beaucoup d'utilisateurs, on laisse Pygal 
            # choisir des paliers (ex: 50, 100, 150...)
            chart.y_labels = None
    
    chart.title = title
    chart.x_labels = labels
    chart.add(title, values)
    chart.render_to_file(os.path.join(OUTPUT_DIR, filename))

def generate_comparison_graphs(parc):
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
    conn = sqlite3.connect(DB_PATH)
    
    metrics = {
        'cpu': {'title': 'Comparaison CPU (%)', 'col': 'cpu_usage', 'is_int': False},
        'ram': {'title': 'Comparaison RAM (%)', 'col': 'ram_usage', 'is_int': False},
        'disk': {'title': 'Comparaison Disque (%)', 'col': 'disk_usage', 'is_int': False},
        'users': {'title': 'Comparaison Utilisateurs (Count)', 'col': 'users_count', 'is_int': True}
    }

    for key, info in metrics.items():
        # Utilisation du style custom pour la cohérence visuelle
        custom_style = DarkStyle(
            background='transparent',
            plot_background='transparent',
            foreground='#ffffff',
            foreground_strong='#ffffff',
            foreground_subtle='#a0a0a0',
            opacity='.6',
            opacity_hover='.9'
        )

        chart = pygal.Line(
            x_label_rotation=20, 
            height=350, 
            style=custom_style, 
            explicit_size_hint=True
        )
        chart.title = info['title']
        
        all_dates = []
        data_found = False
        all_values_for_scale = []

        for machine in parc:
            table_name = machine.replace("-", "").replace("_", "")
            try:
                cursor = conn.cursor()
                cursor.execute(f"SELECT {info['col']}, timestamp FROM {table_name} ORDER BY timestamp DESC LIMIT 15")
                rows = cursor.fetchall()[::-1]
                
                if rows:
                    values = [float(r[0]) for r in rows]
                    dates = [r[1].split()[-1] for r in rows]
                    chart.add(machine, values)
                    all_values_for_scale.extend(values)
                    data_found = True
                    if len(dates) > len(all_dates):
                        all_dates = dates
            except:
                continue
        
        if data_found:
            chart.x_labels = all_dates
            
            #CORRECTION PROTECTION DDOS 
            if info['is_int']:
                max_val = int(max(all_values_for_scale)) if all_values_for_scale else 5
                
                # On limite l'affichage manuel à 15 paliers max
                # Si on dépasse 15, on laisse Pygal gérer l'auto-scaling
                if max_val < 15:
                    chart.y_labels = list(range(0, max_val + 2))
                else:
                    # En cas de DDoS, on ne définit PAS y_labels
                    # Pygal va afficher des paliers intelligents 
                    chart.y_labels = None
           
                
            chart.render_to_file(os.path.join(OUTPUT_DIR, f"compare_{key}.svg"))
            
    conn.close()
def update_all_graphs(parc):
    """Génère les 5 graphiques pour chaque machine du parc."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
    conn = sqlite3.connect(DB_PATH)
    for machine in parc:
        table_name = machine.replace("-", "").replace("_", "")
        try:
            cursor = conn.cursor()
            # Sélection des données
            cursor.execute(f"SELECT cpu_usage, ram_usage, disk_usage, temp, users_count, timestamp FROM {table_name} ORDER BY timestamp DESC LIMIT 20")
            rows = cursor.fetchall()[::-1]

            if rows:
                # On extrait les données (l'ordre dépend de ton SELECT)
                cpu = [r[0] for r in rows]
                ram = [r[1] for r in rows]
                disk = [r[2] for r in rows]
                temp = [r[3] for r in rows]
                users = [r[4] for r in rows]
                dates = [r[5].split()[-1] for r in rows] # Juste l'heure
                
                # Génération des fichiers attendus par app.py
                create_chart("CPU %", dates, cpu, '#00e5ff', f"{table_name}_cpu.svg")
                create_chart("RAM %", dates, ram, '#76ff03', f"{table_name}_ram.svg")
                create_chart("Disque %", dates, disk, '#ffea00', f"{table_name}_disk.svg")
                create_chart("Température °C", dates, temp, '#ff3d00', f"{table_name}_temp.svg")
                create_chart("Utilisateurs", dates, users, '#d500f9', f"{table_name}_users.svg", is_user_chart=True)
                
                print(f"Graphiques mis à jour pour {machine}")
        except Exception as e:
            print(f"Erreur SQL/Pygal pour {machine}: {e}")
    conn.close()

