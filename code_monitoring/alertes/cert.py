#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime, timedelta

#url du site cert
url="http://www.cert.ssi.gouv.fr/"

#recuperer la page web
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

#extraire la derniere alerte
last_alert = soup.find("div",class_="item cert-alert open")

#extraire la date , lelien et le titre de l'alerte
if last_alert:
    alert_date_elem = last_alert.find("span", class_="item-date")
    alert_ref_elem = last_alert.find("div", class_="item-ref")
    alert_title_elem = last_alert.find("div", class_="item-title")

    if alert_date_elem:
       alert_date = alert_date_elem.text.strip()
    else:
       alert_date = "Date non disponible"


    if alert_ref_elem:
       alert_ref = alert_ref_elem.text.strip()
    else:
       alert_ref = "ref non disponible"


    if alert_title_elem:
       alert_title = alert_title_elem.text.strip()

    else:
       alert_title = "titre non disponible"

    alert_text = f"{alert_date} - {alert_title} (Réference : {alert_ref})"
else:
    alert_text = "AUCUNE ALERTE TROUVÉE"

#connexion a la bd
conn = sqlite3.connect("monitoring.db")
cursor = conn.cursor()

#supprimer les laerte plus anciennes que 30 jours
threshold_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

cursor.execute("delete from alerts where timestamp < ?" ,(threshold_date,))
conn.commit


#inserer l'laerfte dans la base
cursor.execute("insert into alerts (message,timestamp) values (?, datetime('now'))" ,(alert_text,))
conn.commit()

conn.close()
print ("derniere alerte cert enregistrée  :",alert_text)
