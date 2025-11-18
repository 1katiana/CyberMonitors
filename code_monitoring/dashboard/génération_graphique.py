#!/usr/bin/env python3

import sqlite3
import pygal
import shutil
from datetime import datetime

# Chemin vers le dossier partagé
shared_folder = "/media/sf_ams_server/"

def save_and_copy(chart, filename):
    chart.render_to_file('static/' + filename)  
    shutil.copy(filename, shared_folder + filename)  

def plot_ram_history():
    conn = sqlite3.connect("monitoring.db")
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, ram_usage FROM system_data ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    conn.close()

    dates = []
    ram_values = []
    for row in rows:
        dates.append(row[0])
        ram_values.append(float(row[1].replace('%', '').strip()))

    chart = pygal.Line(x_label_rotation=20)
    chart.title = 'Utilisation de la RAM dans le temps'
    chart.x_labels = dates
    chart.add('RAM (%)', ram_values)
    save_and_copy(chart, 'ram_history.svg')


def plot_cpu_history():
    conn = sqlite3.connect("monitoring.db")
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, cpu_usage FROM system_data ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    conn.close()

    dates = []
    cpu_values = []
    for row in rows:
        dates.append(row[0])
        cpu_values.append(float(row[1].replace('%', '').strip()))

    chart = pygal.Line(x_label_rotation=20)
    chart.title = 'Utilisation du CPU dans le temps'
    chart.x_labels = dates
    chart.add('CPU (%)', cpu_values)
    save_and_copy(chart, 'cpu_history.svg')


def plot_disk_history():
    conn = sqlite3.connect("monitoring.db")
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, disk_usage FROM system_data ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    conn.close()

    dates = []
    disk_values = []
    for row in rows:
        dates.append(row[0])
        disk_values.append(float(row[1].replace('%', '').strip()))

    chart = pygal.Line(x_label_rotation=20)
    chart.title = 'Utilisation du disque dans le temps'
    chart.x_labels = dates
    chart.add('Disque (%)', disk_values)
    save_and_copy(chart, 'disk_history.svg')


def plot_user_history():
    conn = sqlite3.connect("monitoring.db")
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, users_count FROM system_data ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    conn.close()

    dates = []
    user_counts = []
    for row in rows:
        dates.append(row[0])
        user_counts.append(int(row[1]))

    chart = pygal.Line(x_label_rotation=20)
    chart.title = 'Utilisateurs connectés dans le temps'
    chart.x_labels = dates
    chart.add('Utilisateurs', user_counts)
    save_and_copy(chart, 'users_history.svg')


def plot_process_history():
    conn = sqlite3.connect("monitoring.db")
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, process_count FROM system_data ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    conn.close()

    dates = []
    process_counts = []
    for row in rows:
        dates.append(row[0])
        process_counts.append(int(row[1]))

    chart = pygal.Line(x_label_rotation=20)
    chart.title = 'Processus actifs dans le temps'
    chart.x_labels = dates
    chart.add('Processus', process_counts)
    save_and_copy(chart, 'process_history.svg')


# Lancer tous les graphiques
plot_ram_history()
plot_cpu_history()
plot_disk_history()
plot_user_history()
plot_process_history()
