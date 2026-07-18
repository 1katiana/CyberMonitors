# -*- coding: utf-8 -*-
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from detetction_de_crises.detection_de_crise import load_config
import os

def send_combined_alert(all_crises):
    config = load_config()
    sender = "katianaaoudia23@gmail.com"
    password = os.environ.get("EMAIL_PASSWORD")
    recipients = config["alert_recipients"]

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = f"ALERTE SOC CRITIQUE : {len(all_crises)} Asset(s) en danger"

    # Construction du corps du mail (Ton message conservé à 100%)
    body = "Bonjour,\n\nDes anomalies ont été détectées sur une de vos machines :\n\n"
    for crisis in all_crises:
        body += f" ASSET : {crisis['asset']}\n"
        body += f" HEURE : {crisis['time']}\n"
        body += f" ALERTES : {', '.join(crisis['details'])}\n"
        body += "-------------------------------------------\n"
    body += "\nVeuillez intervenir sur le dashboard : http://localhost:8050"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
            print(f" Email envoyé à : {', '.join(recipients)}")
    except Exception as e:
        print(f" Erreur SMTP: {e}")

# --- NOUVELLE FONCTION POUR L'IAM (Création de compte) ---
def send_email(destinataire, sujet, corps):
    sender = "katianaaoudia23@gmail.com"
    password = os.environ.get("EMAIL_PASSWORD")

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = destinataire
    msg["Subject"] = sujet

    msg.attach(MIMEText(corps, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, [destinataire], msg.as_string())
            print(f" Email de provisioning envoyé à : {destinataire}")
    except Exception as e:
        print(f" Erreur SMTP (send_email): {e}")