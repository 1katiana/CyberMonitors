#!/usr/bin/env python3
from detection_de_crise import fetch_latest_data, check_crisis, load_config
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def load_template():
    with open("email_template.txt", "r") as f:
        return f.read()

def send_email_alert(crises):
    sender = "katianaaoudia23@gmail.com"
    receiver = "katianaaoudia23@gmail.com"
    password = "dptg vvsr depl kcjh"

    subject = "ALERTE : Crise détectée sur le serveur"
    template = load_template()
    body = template.replace("{{crises}}", "\n".join(crises))

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
            print("Alerte envoyée par email.")
    except Exception as e:
        print("Erreur lors de l'envoi de l'email:", e)

# Lancement
config = load_config()
data = fetch_latest_data()
crises = check_crisis(data, config)

if crises:
    send_email_alert(crises)
else:
    print("Aucune crise détectée.")
